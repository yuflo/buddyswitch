#!/usr/bin/env python3
"""Track repository adapters for runtime track persistence access."""

from __future__ import annotations

from typing import Any

import env_legacy_store as env_store

VALID_TRACK_STATE = tuple(env_store.VALID_TRACK_STATE)
VALID_TRACK_HEALTH = tuple(env_store.VALID_TRACK_HEALTH)
VALID_UPDATE_KIND = tuple(env_store.VALID_UPDATE_KIND)


def now_iso() -> str:
    return env_store.now_iso()


def list_tracks() -> list[dict[str, Any]]:
    return env_store.list_tracks()


def get_track(track_id: str) -> dict[str, Any] | None:
    return env_store.get_track(track_id)


def create_track(
    track_id: str,
    title: str,
    *,
    owner_buddy: str = "pm",
    outcome: str = "",
    appetite: str = "1 day",
    now: dict[str, Any] | None = None,
    state: str = "active",
    health: str = "ok",
) -> dict[str, Any]:
    return env_store.create_track(
        track_id,
        title,
        owner_buddy=owner_buddy,
        outcome=outcome,
        appetite=appetite,
        now=now,
        state=state,
        health=health,
    )


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return env_store.update_track(track_id, patch)


def append_track_update(
    *,
    track_id: str,
    by_buddy: str,
    kind: str,
    summary: str,
    refs: list[dict[str, Any]] | None = None,
    update_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return env_store.append_track_update(
        track_id=track_id,
        by_buddy=by_buddy,
        kind=kind,
        summary=summary,
        refs=refs,
        update_id=update_id,
    )


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    return env_store.validate_track(track)


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    return env_store.save_track(track)
