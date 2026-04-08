#!/usr/bin/env python3
"""Build the BuddySwitch console static workspace snapshot."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "framework" / "console" / "workspace-data.js"

ROLE_DIRS = {
    "research": ROOT / "artifacts" / "research",
    "prd": ROOT / "artifacts" / "prd",
    "design": ROOT / "artifacts" / "design",
    "build": ROOT / "artifacts" / "build",
    "test": ROOT / "artifacts" / "test",
}

ROLE_AGENTS = {
    "research": "market",
    "prd": "pm",
    "design": "design",
    "build": "dev",
    "test": "test",
}

GROUP_SUFFIXES = (
    "-market-research",
    "-research-report",
    "-design-spec",
    "-implementation-report",
    "-test-report",
    "-mvp-prd",
    "-smoke-test",
    "-research",
    "-design",
    "-implementation",
    "-smoke",
    "-spec",
    "-impl",
    "-prd",
    "-mvp",
)


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def title_from_markdown(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except UnicodeDecodeError:
        return path.stem
    return path.stem


def group_slug(stem: str) -> str:
    slug = stem
    for suffix in GROUP_SUFFIXES:
        if slug.endswith(suffix) and len(slug) > len(suffix):
            return slug[: -len(suffix)]
    return slug


def empty_artifacts() -> dict[str, list]:
    return {key: [] for key in ROLE_DIRS}


def scan_artifact_groups() -> list[dict]:
    groups: dict[str, dict] = {}

    for role, directory in ROLE_DIRS.items():
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == ".gitkeep":
                continue

            slug = group_slug(path.stem)
            group = groups.setdefault(
                slug,
                {
                    "slug": slug,
                    "label": slug.replace("-", " ").title(),
                    "inferred": True,
                    "inference_source": "artifact_filename",
                    "artifacts": empty_artifacts(),
                    "updated_at": None,
                },
            )

            artifact = {
                "role": role,
                "agent": ROLE_AGENTS[role],
                "inferred_group_slug": slug,
                "path": rel(path),
                "file_name": path.name,
                "title": title_from_markdown(path),
                "updated_at": iso_time(path),
            }
            group["artifacts"][role].append(artifact)

            if group["updated_at"] is None or artifact["updated_at"] > group["updated_at"]:
                group["updated_at"] = artifact["updated_at"]

    for group in groups.values():
        for artifacts in group["artifacts"].values():
            artifacts.sort(key=lambda item: item["updated_at"], reverse=True)

    return sorted(groups.values(), key=lambda item: (item["updated_at"] or "", item["slug"]), reverse=True)


def has_non_research_artifacts(group: dict) -> bool:
    return any(group["artifacts"].get(role) for role in ("prd", "design", "build", "test"))


def classify_artifact_groups(groups: list[dict]) -> tuple[list[dict], list[dict]]:
    tracks = []
    research_inbox = []

    for group in groups:
        item = dict(group)
        item["classification"] = "track" if has_non_research_artifacts(group) else "research_inbox"
        if item["classification"] == "track":
            tracks.append(item)
        else:
            research_inbox.append(item)

    return tracks, research_inbox


def scan_summaries() -> list[dict]:
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


def build_snapshot() -> dict:
    groups = scan_artifact_groups()
    tracks, research_inbox = classify_artifact_groups(groups)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tracks": tracks,
        "research_inbox": research_inbox,
        "summaries": scan_summaries(),
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = build_snapshot()
    payload = "window.BUDDYSWITCH_WORKSPACE = "
    payload += json.dumps(data, ensure_ascii=True, indent=2)
    payload += ";\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    print(
        f"Wrote {rel(OUTPUT)} with {len(data['tracks'])} track(s) "
        f"and {len(data['research_inbox'])} research inbox item(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
