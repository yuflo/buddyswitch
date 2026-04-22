from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


REQUIRED_CONFIG_KEYS = (
    "version",
    "wiki_root",
    "recent_change_window_days",
    "recent_change_max_entries",
    "canonical_sources",
    "maintained_files",
)
SUPPORTED_CONFIG_VERSION = 1


@dataclass(frozen=True)
class RepoWikiConfig:
    version: int
    wiki_root: str
    recent_change_window_days: int
    recent_change_max_entries: int
    canonical_sources: list[str]
    maintained_files: list[str]
    allowed_supporting_globs: list[str]
    owner: str
    notes: str


def _required_key(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"missing required config key: {key}")
    return data[key]


def _required_int(data: dict[str, Any], key: str) -> int:
    value = _required_key(data, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"config key {key} must be an integer")
    return value


def _required_string(data: dict[str, Any], key: str) -> str:
    value = _required_key(data, key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"config key {key} must be a non-empty string")
    return value


def _required_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = _required_key(data, key)
    if not isinstance(value, list):
        raise ValueError(f"config key {key} must be a list of strings")
    if not value:
        raise ValueError(f"config key {key} must not be empty")
    if any((not isinstance(item, str) or not item) for item in value):
        raise ValueError(f"config key {key} must be a list of non-empty strings")
    return list(value)


def _optional_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"optional config key {key} must be a list of strings")
    if any((not isinstance(item, str) or not item) for item in value):
        raise ValueError(f"optional config key {key} must be a list of non-empty strings")
    return list(value)


def _required_positive_int(data: dict[str, Any], key: str) -> int:
    value = _required_int(data, key)
    if value <= 0:
        raise ValueError(f"config key {key} must be greater than 0")
    return value


def _required_supported_version(data: dict[str, Any]) -> int:
    version = _required_int(data, "version")
    if version != SUPPORTED_CONFIG_VERSION:
        raise ValueError(f"config key version must equal {SUPPORTED_CONFIG_VERSION}")
    return version


def _optional_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"optional config key {key} must be a string")
    return value


def _normalized_relative_parts(value: str, key: str) -> tuple[str, ...]:
    if "\\" in value:
        raise ValueError(f"config key {key} must be a canonical relative path")

    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError(f"config key {key} must be a relative path")

    if not path.parts:
        raise ValueError(f"config key {key} must be a non-empty relative path")

    if any(part in (".", "..") for part in path.parts):
        raise ValueError(f"config key {key} must be a canonical relative path")

    canonical = "/".join(path.parts)
    if value != canonical:
        raise ValueError(f"config key {key} must be a canonical relative path")

    return path.parts


def _validate_maintained_files(wiki_root: str, maintained_files: list[str]) -> None:
    wiki_root_parts = _normalized_relative_parts(wiki_root, "wiki_root")

    for item in maintained_files:
        item_parts = _normalized_relative_parts(item, "maintained_files")
        if len(item_parts) <= len(wiki_root_parts) or item_parts[: len(wiki_root_parts)] != wiki_root_parts:
            raise ValueError("config key maintained_files must contain only files under wiki_root")


def _validate_canonical_sources(canonical_sources: list[str]) -> None:
    for item in canonical_sources:
        _normalized_relative_parts(item, "canonical_sources")


def _validate_allowed_supporting_globs(allowed_supporting_globs: list[str]) -> None:
    for item in allowed_supporting_globs:
        if "\\" in item:
            raise ValueError("optional config key allowed_supporting_globs must use canonical forward-slash globs")
        path = PurePosixPath(item)
        if path.is_absolute():
            raise ValueError("optional config key allowed_supporting_globs must be relative globs")
        if not path.parts:
            raise ValueError("optional config key allowed_supporting_globs must be non-empty relative globs")
        if any(part in (".", "..") for part in path.parts):
            raise ValueError("optional config key allowed_supporting_globs must be canonical relative globs")


def load_repo_config(path: Path) -> RepoWikiConfig:
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"config root must be a table: {path}")

    for key in REQUIRED_CONFIG_KEYS:
        _required_key(data, key)

    wiki_root = _required_string(data, "wiki_root")
    version = _required_supported_version(data)
    recent_change_window_days = _required_positive_int(data, "recent_change_window_days")
    recent_change_max_entries = _required_positive_int(data, "recent_change_max_entries")
    canonical_sources = _required_string_list(data, "canonical_sources")
    maintained_files = _required_string_list(data, "maintained_files")
    allowed_supporting_globs = _optional_string_list(data, "allowed_supporting_globs")

    _validate_canonical_sources(canonical_sources)
    _validate_maintained_files(wiki_root, maintained_files)
    _validate_allowed_supporting_globs(allowed_supporting_globs)

    return RepoWikiConfig(
        version=version,
        wiki_root=wiki_root,
        recent_change_window_days=recent_change_window_days,
        recent_change_max_entries=recent_change_max_entries,
        canonical_sources=canonical_sources,
        maintained_files=maintained_files,
        allowed_supporting_globs=allowed_supporting_globs,
        owner=_optional_string(data, "owner"),
        notes=_optional_string(data, "notes"),
    )
