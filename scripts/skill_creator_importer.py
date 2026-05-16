#!/usr/bin/env python3
"""Import a Codex-native skill package into BuddySwitch source."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_buddy


ROOT = Path(__file__).resolve().parents[1]
SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class SkillImportError(ValueError):
    """Raised when a skill import request is invalid or cannot be applied safely."""


@dataclass(frozen=True)
class ImportResult:
    skill_id: str
    buddy_id: str
    package_path: str
    manifest_path: str
    artifact_kind: str | None


def _normalize_source(source: Path) -> tuple[Path, bool]:
    candidate = source.expanduser().resolve(strict=False)
    if not candidate.exists():
        raise SkillImportError(f"source path not found: {source}")
    if candidate.is_file():
        if candidate.name != "SKILL.md":
            raise SkillImportError("direct file import requires a file named SKILL.md")
        return candidate, True
    if not candidate.is_dir():
        raise SkillImportError(f"source must be a directory or SKILL.md file: {source}")
    skill_md = candidate / "SKILL.md"
    if not skill_md.exists() or not skill_md.is_file():
        raise SkillImportError(f"source package is missing SKILL.md: {source}")
    return candidate, False


def _read_skill_md(source_root: Path, direct_skill_file: bool) -> str:
    skill_md = source_root if direct_skill_file else source_root / "SKILL.md"
    return skill_md.read_text(encoding="utf-8")


def _frontmatter_value(skill_text: str, key: str) -> str | None:
    if not skill_text.startswith("---"):
        return None
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        row_key, row_value = stripped.split(":", 1)
        if row_key.strip() != key:
            continue
        value = row_value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        return value.strip() or None
    return None


def _validate_skill_id(skill_id: str) -> str:
    normalized = skill_id.strip()
    if not normalized:
        raise SkillImportError("skill id must be a non-empty string")
    if not SKILL_ID_RE.match(normalized):
        raise SkillImportError(f"invalid skill id '{skill_id}': expected /^[a-z][a-z0-9-]*$/")
    return normalized


def _validate_artifact_kind(artifact_kind: str | None) -> str | None:
    if artifact_kind is None:
        return None
    normalized = artifact_kind.strip()
    if not normalized:
        raise SkillImportError("artifact kind must be a non-empty string when provided")
    if not SKILL_ID_RE.match(normalized):
        raise SkillImportError(f"invalid artifact kind '{artifact_kind}': expected /^[a-z][a-z0-9-]*$/")
    return normalized


def _derive_skill_id(explicit: str | None, skill_text: str, source: Path) -> str:
    if explicit is not None:
        return _validate_skill_id(explicit)

    frontmatter_name = _frontmatter_value(skill_text, "name")
    if frontmatter_name and frontmatter_name.strip():
        raw = frontmatter_name.strip()
    else:
        raw = source.parent.name if source.is_file() else source.name

    lowered = raw.lower()
    lowered = re.sub(r"[\s_]+", "-", lowered)
    lowered = re.sub(r"[^a-z0-9-]", "", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return _validate_skill_id(lowered)


def _copy_source_package(source: Path, direct_skill_file: bool, staging_dir: Path) -> Path:
    if staging_dir.exists():
        if any(staging_dir.iterdir()):
            raise SkillImportError(f"staging directory must be empty: {staging_dir}")
    else:
        staging_dir.mkdir(parents=True, exist_ok=False)
    if direct_skill_file:
        shutil.copy2(source, staging_dir / "SKILL.md")
    else:
        shutil.copytree(source, staging_dir, symlinks=True, dirs_exist_ok=True)

    for retired_metadata in staging_dir.rglob("skill.toml"):
        retired_metadata.unlink()
    return staging_dir


def _append_buddyswitch_rules(skill_md: Path, *, buddy_id: str) -> None:
    original = skill_md.read_text(encoding="utf-8")
    addition = (
        "\n\n## BuddySwitch Runtime Closing Rules\n\n"
        f"- Target BuddySwitch buddy: `{buddy_id}`.\n"
        "- Runtime execution uses env.tool through python3 scripts/env/client.py ... .\n"
        "- Product-readable durable state is written explicitly as task, artifact, or handoff objects.\n"
        "- Use buddybox env tools with `logical_name` for active-buddy-private working files.\n"
        "- Return after required explicit durable writes are complete.\n"
    )
    skill_md.write_text(original.rstrip() + addition, encoding="utf-8")


def _manifest_without_runtime_keys(manifest: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "schema_version": manifest.get("schema_version"),
        "env": dict(manifest.get("env", {})),
    }
    output_skills: list[dict[str, Any]] = []
    for skill in manifest.get("skills", []):
        if not isinstance(skill, dict):
            continue
        cleaned = {key: value for key, value in skill.items() if key != "persistence"}
        output_skills.append(cleaned)
    output["skills"] = output_skills

    output_buddies: list[dict[str, Any]] = []
    for buddy in manifest.get("buddies", []):
        if not isinstance(buddy, dict):
            continue
        output_buddies.append(dict(buddy))
    output["buddies"] = output_buddies
    return output


def _skill_entry(*, skill_id: str, buddy_id: str) -> dict[str, Any]:
    return {
        "id": skill_id,
        "path": f"buddyswitch/skills/{buddy_id}/{skill_id}",
    }


def _toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _format_string_list(values: list[str], *, multiline_threshold: int) -> str:
    if len(values) <= multiline_threshold:
        rendered = ", ".join(_toml_str(item) for item in values)
        return f"[{rendered}]"
    rows = ["["]
    rows.extend(f"  {_toml_str(item)}," for item in values)
    rows.append("]")
    return "\n".join(rows)


def _serialize_manifest(manifest: dict[str, Any]) -> str:
    schema_version = manifest.get("schema_version")
    if not isinstance(schema_version, int):
        raise SkillImportError("manifest.schema_version must be an integer")
    env = manifest.get("env")
    if not isinstance(env, dict):
        raise SkillImportError("manifest.env must be an object")
    env_id = env.get("id")
    env_label = env.get("label")
    if not isinstance(env_id, str) or not env_id.strip():
        raise SkillImportError("manifest.env.id must be a non-empty string")
    if not isinstance(env_label, str) or not env_label.strip():
        raise SkillImportError("manifest.env.label must be a non-empty string")

    skills = manifest.get("skills")
    buddies = manifest.get("buddies")
    if not isinstance(skills, list):
        raise SkillImportError("manifest.skills must be a list")
    if not isinstance(buddies, list):
        raise SkillImportError("manifest.buddies must be a list")

    lines: list[str] = [
        f"schema_version = {schema_version}",
        "",
        "[env]",
        f"id = {_toml_str(env_id.strip())}",
        f"label = {_toml_str(env_label.strip())}",
    ]

    for skill in skills:
        if not isinstance(skill, dict):
            raise SkillImportError("skills entries must be objects")
        skill_id = skill.get("id")
        skill_path = skill.get("path")
        if not isinstance(skill_id, str) or not isinstance(skill_path, str):
            raise SkillImportError("skills entries must include string id and path")
        lines.extend(
            [
                "",
                "[[skills]]",
                f"id = {_toml_str(skill_id)}",
                f"path = {_toml_str(skill_path)}",
            ]
        )

    for buddy in buddies:
        if not isinstance(buddy, dict):
            raise SkillImportError("buddies entries must be objects")
        buddy_id = buddy.get("id")
        label = buddy.get("label")
        scope = buddy.get("scope")
        skills_list = buddy.get("skills")
        artifact_kinds = buddy.get("artifact_kinds")
        permissions = buddy.get("permissions")
        if not isinstance(buddy_id, str) or not isinstance(label, str) or not isinstance(scope, str):
            raise SkillImportError("buddies entries must include id/label/scope strings")
        if not isinstance(skills_list, list) or not all(isinstance(item, str) for item in skills_list):
            raise SkillImportError(f"buddy '{buddy_id}' must include a string skills list")
        if not isinstance(artifact_kinds, list) or not all(isinstance(item, str) for item in artifact_kinds):
            raise SkillImportError(f"buddy '{buddy_id}' must include a string artifact_kinds list")
        if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
            raise SkillImportError(f"buddy '{buddy_id}' must include a string permissions list")

        lines.extend(
            [
                "",
                "[[buddies]]",
                f"id = {_toml_str(buddy_id)}",
                f"label = {_toml_str(label)}",
                f"scope = {_toml_str(scope)}",
            ]
        )

        skills_rendered = _format_string_list(skills_list, multiline_threshold=2)
        if "\n" in skills_rendered:
            lines.append("skills = " + skills_rendered.split("\n", 1)[0])
            lines.extend(skills_rendered.split("\n")[1:])
        else:
            lines.append(f"skills = {skills_rendered}")

        artifact_kinds_rendered = _format_string_list(artifact_kinds, multiline_threshold=3)
        if "\n" in artifact_kinds_rendered:
            lines.append("artifact_kinds = " + artifact_kinds_rendered.split("\n", 1)[0])
            lines.extend(artifact_kinds_rendered.split("\n")[1:])
        else:
            lines.append(f"artifact_kinds = {artifact_kinds_rendered}")

        permissions_rendered = _format_string_list(permissions, multiline_threshold=3)
        if "\n" in permissions_rendered:
            lines.append("permissions = " + permissions_rendered.split("\n", 1)[0])
            lines.extend(permissions_rendered.split("\n")[1:])
        else:
            lines.append(f"permissions = {permissions_rendered}")

    return "\n".join(lines) + "\n"


def _register_skill(
    manifest: dict[str, Any],
    *,
    skill_id: str,
    buddy_id: str,
    artifact_kind: str | None,
) -> dict[str, Any]:
    require_buddy(manifest, buddy_id)
    skills = manifest.get("skills")
    buddies = manifest.get("buddies")
    if not isinstance(skills, list) or not isinstance(buddies, list):
        raise SkillImportError("manifest must include skills and buddies lists")

    for skill in skills:
        if isinstance(skill, dict) and skill.get("id") == skill_id:
            raise SkillImportError(f"skill id already exists in manifest: {skill_id}")

    skills.append(_skill_entry(skill_id=skill_id, buddy_id=buddy_id))
    for buddy in buddies:
        if not isinstance(buddy, dict):
            continue
        raw_id = buddy.get("id")
        if raw_id != buddy_id:
            continue
        raw_skills = buddy.get("skills")
        if not isinstance(raw_skills, list):
            raise SkillImportError(f"buddy '{buddy_id}' skills list is invalid")
        if skill_id not in raw_skills:
            raw_skills.append(skill_id)
        if artifact_kind is not None:
            raw_artifact_kinds = buddy.get("artifact_kinds")
            if not isinstance(raw_artifact_kinds, list):
                raise SkillImportError(f"buddy '{buddy_id}' artifact_kinds list is invalid")
            if artifact_kind not in raw_artifact_kinds:
                raw_artifact_kinds.append(artifact_kind)
        break
    return manifest


def _relative_path_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def import_skill(
    *,
    source: Path,
    buddy_id: str,
    skill_id: str | None = None,
    artifact_kind: str | None = None,
    repo_root: Path = ROOT,
    manifest_path: Path | None = None,
) -> ImportResult:
    repo_root_resolved = repo_root.expanduser().resolve(strict=False)
    if not repo_root_resolved.exists() or not repo_root_resolved.is_dir():
        raise SkillImportError(f"repo_root must exist as a directory: {repo_root}")

    resolved_manifest = manifest_path or (repo_root_resolved / "buddyswitch" / "manifest.toml")
    if not resolved_manifest.is_absolute():
        resolved_manifest = (repo_root_resolved / resolved_manifest).resolve(strict=False)
    source_root, direct_skill_file = _normalize_source(source)
    source_skill_text = _read_skill_md(source_root, direct_skill_file)
    description = _frontmatter_value(source_skill_text, "description")
    if not description:
        raise SkillImportError("source SKILL.md must include non-empty frontmatter description")
    derived_skill_id = _derive_skill_id(skill_id, source_skill_text, source_root)
    normalized_artifact_kind = _validate_artifact_kind(artifact_kind)

    manifest = load_manifest(resolved_manifest)
    require_buddy(manifest, buddy_id)

    target_parent = repo_root_resolved / "buddyswitch" / "skills" / buddy_id
    target_path = target_parent / derived_skill_id
    if target_path.exists():
        raise SkillImportError(f"target package already exists: {target_path}")
    target_parent.mkdir(parents=True, exist_ok=True)

    original_manifest_bytes = resolved_manifest.read_bytes()
    staging_path: Path | None = None
    temp_manifest_path: Path | None = None
    target_created = False
    manifest_replaced = False

    try:
        staging_path = Path(
            tempfile.mkdtemp(prefix=f".{derived_skill_id}.import-", dir=target_parent)
        )
        _copy_source_package(source_root, direct_skill_file, staging_path)
        staged_skill_md = staging_path / "SKILL.md"
        if not staged_skill_md.exists():
            raise SkillImportError("staged package is missing SKILL.md")
        _append_buddyswitch_rules(
            staged_skill_md,
            buddy_id=buddy_id,
        )

        manifest_without_runtime = _manifest_without_runtime_keys(manifest)
        updated_manifest = _register_skill(
            manifest_without_runtime,
            skill_id=derived_skill_id,
            buddy_id=buddy_id,
            artifact_kind=normalized_artifact_kind,
        )
        updated_text = _serialize_manifest(updated_manifest)

        fd, temp_manifest_raw = tempfile.mkstemp(
            prefix=".manifest.import-",
            suffix=".toml",
            dir=resolved_manifest.parent,
        )
        os.close(fd)
        temp_manifest_path = Path(temp_manifest_raw)
        temp_manifest_path.write_text(updated_text, encoding="utf-8")
        load_manifest(temp_manifest_path)

        os.replace(staging_path, target_path)
        target_created = True
        os.replace(temp_manifest_path, resolved_manifest)
        manifest_replaced = True
    except Exception as exc:
        if staging_path is not None and staging_path.exists():
            shutil.rmtree(staging_path, ignore_errors=True)
        if target_created and target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)
        if temp_manifest_path is not None and temp_manifest_path.exists():
            temp_manifest_path.unlink(missing_ok=True)
        if manifest_replaced or resolved_manifest.read_bytes() != original_manifest_bytes:
            fd, restore_raw = tempfile.mkstemp(
                prefix=".manifest.restore-",
                suffix=".toml",
                dir=resolved_manifest.parent,
            )
            os.close(fd)
            restore_path = Path(restore_raw)
            restore_path.write_bytes(original_manifest_bytes)
            os.replace(restore_path, resolved_manifest)
        if isinstance(exc, SkillImportError):
            raise
        if isinstance(exc, ManifestError):
            raise SkillImportError(str(exc)) from exc
        raise SkillImportError(str(exc)) from exc

    return ImportResult(
        skill_id=derived_skill_id,
        buddy_id=buddy_id,
        package_path=f"buddyswitch/skills/{buddy_id}/{derived_skill_id}",
        manifest_path=_relative_path_or_absolute(resolved_manifest, repo_root_resolved),
        artifact_kind=normalized_artifact_kind,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a Codex-native skill package into BuddySwitch.")
    parser.add_argument("--source", type=Path, required=True, help="Source package directory or SKILL.md file")
    parser.add_argument("--buddy", required=True, help="Target buddy id")
    parser.add_argument("--skill-id", help="Optional explicit generated skill id")
    parser.add_argument("--artifact-kind", help="Optional buddy artifact kind to append for this imported skill")
    parser.add_argument("--manifest", type=Path, help="Manifest path (default: buddyswitch/manifest.toml under repo root)")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Repo root containing buddyswitch/manifest.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = import_skill(
            source=args.source,
            buddy_id=args.buddy,
            skill_id=args.skill_id,
            artifact_kind=args.artifact_kind,
            repo_root=args.repo_root,
            manifest_path=args.manifest,
        )
    except (SkillImportError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "skill_id": result.skill_id,
                "buddy_id": result.buddy_id,
                "package_path": result.package_path,
                "manifest_path": result.manifest_path,
                "artifact_kind": result.artifact_kind,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
