#!/usr/bin/env python3
"""Actor-local model config pathing, validation, seeding, and resolution."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


MODEL_CONFIG_FILENAME = "model-config.json"
SCHEMA_VERSION = 1
VALID_EFFORTS = {"minimal", "low", "medium", "high", "ultra"}
_TOP_LEVEL_KEYS = {"schema_version", "parent", "side"}
_SECTION_KEYS = {"model", "effort"}
_DEFAULT_PAYLOAD = {
    "schema_version": SCHEMA_VERSION,
    "parent": {},
    "side": {},
}


class ActorModelConfigError(RuntimeError):
    """Raised when actor model config cannot be loaded or validated."""


@dataclass(frozen=True)
class ActorModelConfig:
    schema_version: int
    parent: dict[str, str]
    side: dict[str, str]


@dataclass(frozen=True)
class ResolvedModelOptions:
    model: str | None = None
    effort: str | None = None
    model_source: str = "codex_default"
    effort_source: str = "codex_default"

    @property
    def has_values(self) -> bool:
        return self.model is not None or self.effort is not None


def model_config_path(instance_json: Path) -> Path:
    return instance_json.parent / MODEL_CONFIG_FILENAME


def seed_model_config_if_missing(instance_json: Path) -> Path:
    path = model_config_path(instance_json)
    if path.exists():
        return path
    path.write_text(json.dumps(_DEFAULT_PAYLOAD, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return path


def load_model_config(instance_json: Path) -> ActorModelConfig:
    path = model_config_path(instance_json)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ActorModelConfig(schema_version=SCHEMA_VERSION, parent={}, side={})
    except OSError as exc:
        raise ActorModelConfigError(f"{path}: failed to read model config: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActorModelConfigError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ActorModelConfigError(f"{path}: model config must be an object")
    return _validate_payload(path, payload)


def resolve_parent_options(instance_json: Path) -> ResolvedModelOptions:
    config = load_model_config(instance_json)
    return _resolved_options(config.parent, explicit_model=None, explicit_effort=None)


def resolve_side_options(
    instance_json: Path,
    *,
    explicit_model: str | None = None,
    explicit_effort: str | None = None,
) -> ResolvedModelOptions:
    config = load_model_config(instance_json)
    return _resolved_options(config.side, explicit_model=explicit_model, explicit_effort=explicit_effort)


def apply_side_source_metadata(payload: Mapping[str, Any], options: ResolvedModelOptions) -> dict[str, Any]:
    result = dict(payload)
    if options.model is None:
        result.pop("model", None)
    else:
        result["model"] = options.model
    if options.effort is None:
        result.pop("model_reasoning_effort", None)
    else:
        result["model_reasoning_effort"] = options.effort
    result["model_source"] = options.model_source
    result["model_reasoning_effort_source"] = options.effort_source
    result["model_config_durability"] = "thread_fork_only"
    return result


def _validate_payload(path: Path, payload: Mapping[str, Any]) -> ActorModelConfig:
    unknown = set(payload) - _TOP_LEVEL_KEYS
    if unknown:
        raise ActorModelConfigError(f"{path}: unknown top-level model config key: {sorted(unknown)[0]}")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise ActorModelConfigError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    parent = _validate_section(path, payload.get("parent", {}), "parent")
    side = _validate_section(path, payload.get("side", {}), "side")
    return ActorModelConfig(schema_version=SCHEMA_VERSION, parent=parent, side=side)


def _validate_section(path: Path, value: Any, section_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ActorModelConfigError(f"{path}: {section_name} must be an object")
    unknown = set(value) - _SECTION_KEYS
    if unknown:
        raise ActorModelConfigError(f"{path}: unknown {section_name} model config key: {sorted(unknown)[0]}")
    result: dict[str, str] = {}
    if "model" in value:
        result["model"] = _normalize_model(value.get("model"), f"{section_name}.model", path=path)
    if "effort" in value:
        result["effort"] = _normalize_effort(value.get("effort"), f"{section_name}.effort", path=path)
    return result


def _resolved_options(
    section: Mapping[str, str],
    *,
    explicit_model: str | None,
    explicit_effort: str | None,
) -> ResolvedModelOptions:
    model = section.get("model")
    effort = section.get("effort")
    model_source = "actor_config" if model is not None else "codex_default"
    effort_source = "actor_config" if effort is not None else "codex_default"

    if explicit_model is not None:
        model = _normalize_model(explicit_model, "explicit_model")
        model_source = "override"
    if explicit_effort is not None:
        effort = _normalize_effort(explicit_effort, "explicit_effort")
        effort_source = "override"

    return ResolvedModelOptions(
        model=model,
        effort=effort,
        model_source=model_source,
        effort_source=effort_source,
    )


def _normalize_model(value: Any, field_name: str, *, path: Path | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActorModelConfigError(_field_error(field_name, "must be a non-empty string", path=path))
    return value.strip()


def _normalize_effort(value: Any, field_name: str, *, path: Path | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActorModelConfigError(_field_error(field_name, "must be a non-empty string", path=path))
    normalized = value.strip()
    if normalized not in VALID_EFFORTS:
        allowed = ", ".join(sorted(VALID_EFFORTS))
        raise ActorModelConfigError(_field_error(field_name, f"must be one of: {allowed}", path=path))
    return normalized


def _field_error(field_name: str, message: str, *, path: Path | None) -> str:
    prefix = f"{path}: " if path is not None else ""
    return f"{prefix}{field_name} {message}"


def _command_seed(args: argparse.Namespace) -> int:
    path = seed_model_config_if_missing(Path(args.instance_json))
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed")
    seed.add_argument("--instance-json", required=True)
    seed.set_defaults(func=_command_seed)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ActorModelConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
