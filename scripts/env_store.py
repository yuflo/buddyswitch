#!/usr/bin/env python3
"""Runtime-root compatibility bindings for BuddySwitch env runtime.

`env_store` no longer exposes object CRUD/publication helpers. Runtime and tests
that still need legacy object APIs must import `env_legacy_store`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.repos import runtime_files

ROOT: Path
WORKSPACE_ROOT: Path
STATE_ROOT: Path
OBJECTS_ROOT: Path
TRACKS_DIR: Path
ARTIFACT_OBJECTS_DIR: Path
MESSAGES_DIR: Path
COMMENTS_DIR: Path
CONTENT_ROOT: Path
LOCAL_ROOT: Path
ACTOR_PRIVATE_DIR: Path


def refresh_runtime_root_bindings() -> None:
    """Keep compatibility globals synced with runtime_files root bindings."""

    global ROOT
    global WORKSPACE_ROOT
    global STATE_ROOT
    global OBJECTS_ROOT
    global TRACKS_DIR
    global ARTIFACT_OBJECTS_DIR
    global MESSAGES_DIR
    global COMMENTS_DIR
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
    COMMENTS_DIR = runtime_files.COMMENTS_DIR
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
set_runtime_root_override = runtime_files.set_runtime_root_override
reset_runtime_root_override = runtime_files.reset_runtime_root_override

_RETIRED_TASK_APIS = frozenset(
    {
        "VALID_TASK_STATUS",
        "task_file",
        "validate_task",
        "list_tasks",
        "get_task",
        "save_task",
        "create_task",
        "update_task",
    }
)

_RETIRED_OBJECT_APIS = frozenset(
    {
        "VALID_TRACK_STATE",
        "VALID_TRACK_HEALTH",
        "VALID_UPDATE_KIND",
        "VALID_ARTIFACT_STATUS",
        "VALID_ARTIFACT_TEMPLATES",
        "track_file",
        "artifact_file",
        "message_file",
        "comment_file",
        "validate_track",
        "validate_artifact",
        "validate_message",
        "validate_comment",
        "list_tracks",
        "list_artifacts",
        "artifact_revision_chain",
        "build_track_artifact_index",
        "get_track",
        "get_artifact",
        "save_track",
        "save_artifact",
        "create_track",
        "update_track",
        "create_artifact_revision",
        "update_artifact",
        "publish_track_material",
        "publish_track_proof",
        "append_track_update",
        "delete_artifact",
        "delete_artifacts_by_role",
        "delete_all_artifacts",
        "list_messages",
        "get_message",
        "save_message",
        "create_message",
        "list_comments",
        "get_comment",
        "save_comment",
        "create_comment",
        "comments_for_target",
        "update_comment_thread_status",
    }
)


def __getattr__(name: str) -> Any:
    if name in _RETIRED_TASK_APIS:
        raise AttributeError(
            f"env_store.{name} is retired; use env.repos.tasks with explicit instance context"
        )
    if name in _RETIRED_OBJECT_APIS:
        raise AttributeError(
            f"env_store.{name} is retired; import env_legacy_store.{name} for legacy object APIs"
        )
    raise AttributeError(f"module 'env_store' has no attribute '{name}'")


__all__ = [
    "ROOT",
    "WORKSPACE_ROOT",
    "STATE_ROOT",
    "OBJECTS_ROOT",
    "TRACKS_DIR",
    "ARTIFACT_OBJECTS_DIR",
    "MESSAGES_DIR",
    "COMMENTS_DIR",
    "CONTENT_ROOT",
    "LOCAL_ROOT",
    "ACTOR_PRIVATE_DIR",
    "RUNTIME_WORKSPACE_AGENTS_HEADER",
    "refresh_runtime_root_bindings",
    "now_iso",
    "runtime_workspace_root",
    "actor_private_dir",
    "refresh_runtime_roots_from_env",
    "rel",
    "runtime_workspace_agents_file",
    "is_runtime_workspace",
    "require_runtime_workspace_write_root",
    "ensure_runtime_dirs",
    "require_id",
    "slugify",
    "set_runtime_root_override",
    "reset_runtime_root_override",
]
