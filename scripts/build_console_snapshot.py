#!/usr/bin/env python3
"""Build the BuddySwitch console static workspace snapshot."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "artifacts" / "workspace-registry.json"
OUTPUT = ROOT / "framework" / "console" / "workspace-data.js"

ROLE_ORDER = ("market", "pm", "design", "dev", "test")

ARTIFACT_DIRS = {
    "research": {"path": ROOT / "artifacts" / "research", "role": "market", "type": "research"},
    "prd": {"path": ROOT / "artifacts" / "prd", "role": "pm", "type": "prd"},
    "design": {"path": ROOT / "artifacts" / "design", "role": "design", "type": "design-spec"},
    "build": {"path": ROOT / "artifacts" / "build", "role": "dev", "type": "implementation-report"},
    "test": {"path": ROOT / "artifacts" / "test", "role": "test", "type": "smoke-test"},
}


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_registry_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Registry artifact path must be repo-relative: {raw_path}")
    return path.as_posix()


def title_from_markdown(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except UnicodeDecodeError:
        return path.stem
    return path.stem


def empty_artifacts() -> dict[str, list[dict[str, Any]]]:
    return {role: [] for role in ROLE_ORDER}


def artifact_defaults(path: str) -> dict[str, str]:
    for source_dir, config in ARTIFACT_DIRS.items():
        prefix = f"artifacts/{source_dir}/"
        if path.startswith(prefix):
            return {"source_dir": source_dir, "role": config["role"], "type": config["type"]}
    return {"source_dir": "unknown", "role": "unknown", "type": "unknown"}


def artifact_metadata(path: str, role: str | None = None, artifact_type: str | None = None) -> dict[str, Any]:
    normalized = normalize_registry_path(path)
    defaults = artifact_defaults(normalized)
    resolved = ROOT / normalized
    exists = resolved.exists()

    return {
        "role": role or defaults["role"],
        "type": artifact_type or defaults["type"],
        "source_dir": defaults["source_dir"],
        "path": normalized,
        "file_name": Path(normalized).name,
        "title": title_from_markdown(resolved) if exists else Path(normalized).stem,
        "updated_at": iso_time(resolved) if exists else None,
        "missing": not exists,
    }


def load_registry() -> dict[str, Any]:
    if not REGISTRY.exists():
        project_id = ROOT.name
        project_name = "BuddySwitch" if project_id == "buddyswitch" else project_id.replace("-", " ").title()
        return {
            "schema_version": 1,
            "project": {"id": project_id, "name": project_name},
            "tracks": [],
        }

    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {rel(REGISTRY)}: {exc}") from exc

    if registry.get("schema_version") != 1:
        raise ValueError("Registry schema_version must be 1.")
    if not isinstance(registry.get("tracks"), list):
        raise ValueError("Registry tracks must be a list.")
    return registry


def build_tracks(registry: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    tracks: list[dict[str, Any]] = []
    registered_paths: set[str] = set()

    for raw_track in registry["tracks"]:
        if not isinstance(raw_track, dict):
            raise ValueError("Each registry track must be an object.")

        track_id = raw_track.get("id")
        if not isinstance(track_id, str) or not track_id:
            raise ValueError("Each registry track must include a non-empty id.")

        artifacts = empty_artifacts()
        missing_artifacts: list[str] = []
        updated_at: str | None = None

        raw_artifacts = raw_track.get("artifacts", [])
        if not isinstance(raw_artifacts, list):
            raise ValueError(f"Track {track_id} artifacts must be a list.")

        for ref in raw_artifacts:
            if not isinstance(ref, dict):
                raise ValueError(f"Track {track_id} has an artifact entry that is not an object.")

            raw_path = ref.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                raise ValueError(f"Track {track_id} has an artifact without a path.")

            role = ref.get("role")
            if role not in ROLE_ORDER:
                raise ValueError(f"Track {track_id} has an artifact with invalid role: {role}")

            metadata = artifact_metadata(raw_path, role=role, artifact_type=ref.get("type"))
            registered_paths.add(metadata["path"])
            artifacts[role].append(metadata)

            if metadata["missing"]:
                missing_artifacts.append(metadata["path"])
            elif updated_at is None or metadata["updated_at"] > updated_at:
                updated_at = metadata["updated_at"]

        for role_artifacts in artifacts.values():
            role_artifacts.sort(key=lambda item: item["updated_at"] or "", reverse=True)

        tracks.append(
            {
                "id": track_id,
                "title": raw_track.get("title") or track_id.replace("-", " ").title(),
                "state": raw_track.get("state") or "active",
                "artifacts": artifacts,
                "updated_at": updated_at,
                "missing_artifacts": missing_artifacts,
                "registry_path": rel(REGISTRY),
            }
        )

    tracks.sort(key=lambda item: (item["updated_at"] or "", item["id"]), reverse=True)
    return tracks, registered_paths


def scan_artifact_files() -> list[dict[str, Any]]:
    artifacts = []
    for source_dir, config in ARTIFACT_DIRS.items():
        directory = config["path"]
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            artifacts.append(artifact_metadata(rel(path), role=config["role"], artifact_type=config["type"]))
    return sorted(artifacts, key=lambda item: (item["updated_at"] or "", item["path"]), reverse=True)


def scan_untracked_artifacts(registered_paths: set[str]) -> list[dict[str, Any]]:
    return [artifact for artifact in scan_artifact_files() if artifact["path"] not in registered_paths]


def scan_summaries() -> list[dict[str, Any]]:
    directory = ROOT / "runs" / "summaries"
    if not directory.exists():
        return []

    summaries = []
    for path in sorted(directory.glob("*.md")):
        if path.name == ".gitkeep":
            continue
        summaries.append(
            {
                "path": rel(path),
                "file_name": path.name,
                "title": title_from_markdown(path),
                "updated_at": iso_time(path),
            }
        )
    return sorted(summaries, key=lambda item: item["updated_at"], reverse=True)


def build_snapshot() -> dict[str, Any]:
    registry = load_registry()
    tracks, registered_paths = build_tracks(registry)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "registry_path": rel(REGISTRY),
        "project": registry.get("project", {}),
        "tracks": tracks,
        "untracked_artifacts": scan_untracked_artifacts(registered_paths),
        "summaries": scan_summaries(),
    }


def main() -> int:
    try:
        data = build_snapshot()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = "window.BUDDYSWITCH_WORKSPACE = "
    payload += json.dumps(data, ensure_ascii=True, indent=2)
    payload += ";\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    print(
        f"Wrote {rel(OUTPUT)} with {len(data['tracks'])} track(s) "
        f"and {len(data['untracked_artifacts'])} untracked artifact(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
