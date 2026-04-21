#!/usr/bin/env python3
"""Repository entrypoints delegating to env_store legacy implementations."""

from __future__ import annotations

from typing import Any


def build_track_artifact_index(track_id: str | None) -> dict[str, Any] | None:
    import env_store

    return env_store._legacy_build_track_artifact_index(track_id)


def list_tracks() -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_list_tracks()


def list_tasks() -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_list_tasks()


def list_artifacts() -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_list_artifacts()


def list_task_artifacts(task_id: str) -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_list_task_artifacts(task_id)


def get_track(track_id: str) -> dict[str, Any] | None:
    import env_store

    return env_store._legacy_get_track(track_id)


def get_task(task_id: str) -> dict[str, Any] | None:
    import env_store

    return env_store._legacy_get_task(task_id)


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    import env_store

    return env_store._legacy_get_artifact(artifact_id)


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    import env_store

    return env_store._legacy_save_track(track)


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    import env_store

    return env_store._legacy_save_task(task)


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    import env_store

    return env_store._legacy_save_artifact(artifact)


def create_track(
    track_id: str,
    title: str,
    *,
    status: str = "active",
    current_buddy: str = "pm",
    next_buddy: str | None = None,
    summary: str = "",
) -> dict[str, Any]:
    import env_store

    return env_store._legacy_create_track(
        track_id,
        title,
        status=status,
        current_buddy=current_buddy,
        next_buddy=next_buddy,
        summary=summary,
    )


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    import env_store

    return env_store._legacy_update_track(track_id, patch)


def advance_track(
    track_id: str,
    *,
    next_buddy: str,
    summary: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    import env_store

    return env_store._legacy_advance_track(
        track_id,
        next_buddy=next_buddy,
        summary=summary,
        status=status,
    )


def create_task(
    task_id: str,
    title: str,
    *,
    buddy: str,
    track_id: str | None = None,
    status: str = "active",
    summary: str = "",
    initial_run_id: str,
) -> dict[str, Any]:
    import env_store

    return env_store._legacy_create_task(
        task_id,
        title,
        buddy=buddy,
        track_id=track_id,
        status=status,
        summary=summary,
        initial_run_id=initial_run_id,
    )


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    import env_store

    return env_store._legacy_update_task(task_id, patch)


def register_task_to_track(track_id: str, task_id: str) -> dict[str, Any]:
    import env_store

    return env_store._legacy_register_task_to_track(track_id, task_id)


def add_run_to_task(task_id: str, run_id: str, *, summary: str | None = None) -> dict[str, Any]:
    import env_store

    return env_store._legacy_add_run_to_task(task_id, run_id, summary=summary)


def add_artifact_to_task(task_id: str, artifact_id: str, *, summary: str | None = None) -> dict[str, Any]:
    import env_store

    return env_store._legacy_add_artifact_to_task(task_id, artifact_id, summary=summary)


def remove_artifact_from_task(task_id: str, artifact_id: str) -> dict[str, Any]:
    import env_store

    return env_store._legacy_remove_artifact_from_task(task_id, artifact_id)


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    buddy: str,
    skill_id: str,
    slot: str | None = None,
    task_id: str,
    source_run_id: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    auto_register: bool = True,
) -> dict[str, Any]:
    import env_store

    return env_store._legacy_create_artifact(
        artifact_id=artifact_id,
        title=title,
        buddy=buddy,
        skill_id=skill_id,
        slot=slot,
        task_id=task_id,
        source_run_id=source_run_id,
        summary=summary,
        content=content,
        auto_register=auto_register,
    )


def update_artifact(
    artifact_id: str,
    patch: dict[str, Any],
    *,
    auto_register: bool = True,
) -> dict[str, Any]:
    import env_store

    return env_store._legacy_update_artifact(
        artifact_id,
        patch,
        auto_register=auto_register,
    )


def delete_artifact(artifact_id: str, *, delete_file: bool = False) -> dict[str, Any]:
    import env_store

    return env_store._legacy_delete_artifact(artifact_id, delete_file=delete_file)


def delete_artifacts_by_buddy(
    buddy_id: str,
    *,
    delete_files: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_delete_artifacts_by_buddy(
        buddy_id,
        delete_files=delete_files,
        dry_run=dry_run,
    )


def delete_all_artifacts(*, delete_files: bool = False, dry_run: bool = False) -> list[dict[str, Any]]:
    import env_store

    return env_store._legacy_delete_all_artifacts(delete_files=delete_files, dry_run=dry_run)


def save_run_content(run_id: str, payload: dict[str, Any]) -> str:
    import env_store

    return env_store._legacy_save_run_content(run_id, payload)
