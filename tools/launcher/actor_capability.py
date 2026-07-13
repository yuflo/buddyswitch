"""Actor-local capability catalog, persistence, and runtime resolution."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CAPABILITY_CONFIG_FILENAME = "capability-config.json"
SCHEMA_VERSION = 1
CATALOG_VERSION = 1
DEFAULT_PARENT_LEVEL = "balanced"
DEFAULT_SIDE_LEVEL = "fast"
_TOP_LEVEL_KEYS = {"schema_version", "catalog_version", "parent", "side"}
_SNAPSHOT_KEYS = {"level", "model", "effort"}


@dataclass(frozen=True)
class CapabilityProfile:
    id: str
    label: str
    description: str
    model: str
    effort: str


CAPABILITY_LEVELS = (
    CapabilityProfile("fast", "Fast", "Responsive, high-strength reasoning", "gpt-5.6-luna", "xhigh"),
    CapabilityProfile("balanced", "Balanced", "Strong everyday work", "gpt-5.6-terra", "high"),
    CapabilityProfile("deep", "Deep", "Complex reasoning and coding", "gpt-5.6-sol", "xhigh"),
    CapabilityProfile("maximum", "Maximum", "Highest capability and cost", "gpt-5.6-sol", "max"),
)
_PROFILE_BY_ID = {profile.id: profile for profile in CAPABILITY_LEVELS}


class ActorCapabilityError(RuntimeError):
    """Raised when actor capabilities cannot be loaded, validated, or saved."""


@dataclass(frozen=True)
class CapabilitySnapshot:
    level: str
    model: str
    effort: str


@dataclass(frozen=True)
class ActorCapabilities:
    schema_version: int
    catalog_version: int
    parent: CapabilitySnapshot
    side: CapabilitySnapshot


@dataclass(frozen=True)
class ResolvedCapability:
    level: str
    model: str
    effort: str
    source: str
    catalog_version: int


def capability_config_path(instance_json: Path) -> Path:
    return instance_json.parent / CAPABILITY_CONFIG_FILENAME


def seed_actor_capabilities(instance_json: Path) -> Path:
    path = capability_config_path(instance_json)
    if path.exists():
        return path
    _atomic_write_json(path, _disk_payload(_config_for_levels(DEFAULT_PARENT_LEVEL, DEFAULT_SIDE_LEVEL)))
    return path


def load_actor_capabilities(instance_json: Path) -> ActorCapabilities:
    path = capability_config_path(instance_json)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ActorCapabilityError(f"{path}: capability config is missing") from exc
    except OSError as exc:
        raise ActorCapabilityError(f"{path}: failed to read capability config: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActorCapabilityError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ActorCapabilityError(f"{path}: capability config must be an object")
    unknown = set(payload) - _TOP_LEVEL_KEYS
    if unknown:
        raise ActorCapabilityError(f"{path}: unknown top-level capability config key: {sorted(unknown)[0]}")
    missing = _TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ActorCapabilityError(f"{path}: missing capability config key: {sorted(missing)[0]}")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise ActorCapabilityError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    catalog_version = payload.get("catalog_version")
    if type(catalog_version) is not int or catalog_version < 1:
        raise ActorCapabilityError(f"{path}: catalog_version must be a positive integer")
    return ActorCapabilities(
        schema_version=SCHEMA_VERSION,
        catalog_version=catalog_version,
        parent=_load_snapshot(path, payload["parent"], "parent"),
        side=_load_snapshot(path, payload["side"], "side"),
    )


def replace_actor_capabilities(
    instance_json: Path,
    *,
    parent_level: str,
    side_level: str,
) -> ActorCapabilities:
    config = _config_for_levels(parent_level, side_level)
    _atomic_write_json(capability_config_path(instance_json), _disk_payload(config))
    return config


def describe_actor_capabilities(config: ActorCapabilities) -> dict[str, Any]:
    def catalog_row(profile: CapabilityProfile) -> dict[str, str]:
        return {
            "id": profile.id,
            "label": profile.label,
            "description": profile.description,
            "model": profile.model,
            "effort": profile.effort,
        }

    def selection(snapshot: CapabilitySnapshot, effect: str) -> dict[str, str]:
        return {
            "level": snapshot.level,
            "model": snapshot.model,
            "effort": snapshot.effort,
            "effect": effect,
        }

    return {
        "catalog_version": config.catalog_version,
        "levels": [catalog_row(profile) for profile in CAPABILITY_LEVELS],
        "parent": selection(config.parent, "applies_before_next_parent_submit"),
        "side": selection(config.side, "applies_to_new_side_threads_only"),
    }


def resolve_parent_capability(instance_json: Path) -> ResolvedCapability:
    config = load_actor_capabilities(instance_json)
    return ResolvedCapability(
        level=config.parent.level,
        model=config.parent.model,
        effort=config.parent.effort,
        source="actor_config",
        catalog_version=config.catalog_version,
    )


def resolve_side_capability(
    instance_json: Path,
    *,
    explicit_level: str | None = None,
) -> ResolvedCapability:
    config = load_actor_capabilities(instance_json)
    if explicit_level is None:
        snapshot = config.side
        source = "actor_config"
        catalog_version = config.catalog_version
    else:
        snapshot = _snapshot_for_level(explicit_level, "explicit_level")
        source = "override"
        catalog_version = CATALOG_VERSION
    return ResolvedCapability(
        level=snapshot.level,
        model=snapshot.model,
        effort=snapshot.effort,
        source=source,
        catalog_version=catalog_version,
    )


def apply_side_capability_metadata(
    payload: Mapping[str, Any],
    resolved: ResolvedCapability,
) -> dict[str, Any]:
    result = dict(payload)
    result["model"] = resolved.model
    result["model_reasoning_effort"] = resolved.effort
    result["capability_level"] = resolved.level
    result["capability_source"] = resolved.source
    result["capability_durability"] = "thread_fork_only"
    return result


def _profile_for_level(level: Any, field_name: str, *, path: Path | None = None) -> CapabilityProfile:
    if not isinstance(level, str) or not level.strip():
        raise ActorCapabilityError(_field_error(field_name, "must be a non-empty string", path=path))
    normalized = level.strip()
    profile = _PROFILE_BY_ID.get(normalized)
    if profile is None:
        allowed = ", ".join(profile.id for profile in CAPABILITY_LEVELS)
        raise ActorCapabilityError(_field_error(field_name, f"must be one of: {allowed}", path=path))
    return profile


def _snapshot_for_level(level: str, field_name: str) -> CapabilitySnapshot:
    profile = _profile_for_level(level, field_name)
    return CapabilitySnapshot(level=profile.id, model=profile.model, effort=profile.effort)


def _config_for_levels(parent_level: str, side_level: str) -> ActorCapabilities:
    return ActorCapabilities(
        schema_version=SCHEMA_VERSION,
        catalog_version=CATALOG_VERSION,
        parent=_snapshot_for_level(parent_level, "parent_level"),
        side=_snapshot_for_level(side_level, "side_level"),
    )


def _load_snapshot(path: Path, value: Any, section_name: str) -> CapabilitySnapshot:
    if not isinstance(value, dict):
        raise ActorCapabilityError(f"{path}: {section_name} must be an object")
    unknown = set(value) - _SNAPSHOT_KEYS
    if unknown:
        raise ActorCapabilityError(f"{path}: unknown {section_name} capability key: {sorted(unknown)[0]}")
    missing = _SNAPSHOT_KEYS - set(value)
    if missing:
        expected = ", ".join(sorted(_SNAPSHOT_KEYS))
        raise ActorCapabilityError(f"{path}: {section_name} must contain exactly: {expected}")
    profile = _profile_for_level(value["level"], f"{section_name}.level", path=path)
    model = _non_empty_text(value["model"], f"{section_name}.model", path=path)
    effort = _non_empty_text(value["effort"], f"{section_name}.effort", path=path)
    return CapabilitySnapshot(level=profile.id, model=model, effort=effort)


def _non_empty_text(value: Any, field_name: str, *, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActorCapabilityError(_field_error(field_name, "must be a non-empty string", path=path))
    return value.strip()


def _field_error(field_name: str, message: str, *, path: Path | None) -> str:
    prefix = f"{path}: " if path is not None else ""
    return f"{prefix}{field_name} {message}"


def _disk_payload(config: ActorCapabilities) -> dict[str, Any]:
    def section(snapshot: CapabilitySnapshot) -> dict[str, str]:
        return {"level": snapshot.level, "model": snapshot.model, "effort": snapshot.effort}

    return {
        "schema_version": config.schema_version,
        "catalog_version": config.catalog_version,
        "parent": section(config.parent),
        "side": section(config.side),
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{CAPABILITY_CONFIG_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise ActorCapabilityError(f"{path}: failed to write capability config: {exc}") from exc
