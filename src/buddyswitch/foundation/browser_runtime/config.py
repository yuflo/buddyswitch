"""Single host-global configuration for Browser Foundation TTL scheduling."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from typing import TextIO


SCHEMA_VERSION = 1
DEFAULT_CONFIG_TEXT = """schema_version = 1

[ttl]
page_idle_seconds = 40
release_delay_seconds = 10
"""
TOP_LEVEL_KEYS = {"schema_version", "ttl"}
TTL_KEYS = {"page_idle_seconds", "release_delay_seconds"}


class BrowserTtlConfigError(RuntimeError):
    """Raised when the one browser TTL config is missing or invalid."""


@dataclass(frozen=True)
class BrowserTtlConfig:
    page_idle_seconds: int
    release_delay_seconds: int


def _shared_root_from_instance(instance_root: Path) -> Path:
    root = Path(instance_root)
    if root.parent.name != "instances":
        raise BrowserTtlConfigError(
            f"browser instance root must be <shared-root>/instances/<actor-id>: {root}"
        )
    return root.parent.parent


def browser_ttl_config_path(
    *,
    shared_root: Path | None = None,
    instance_root: Path | None = None,
) -> Path:
    if shared_root is not None and instance_root is not None:
        raise BrowserTtlConfigError("provide shared_root or instance_root, not both")
    if shared_root is None:
        if instance_root is not None:
            shared_root = _shared_root_from_instance(instance_root)
        else:
            raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT", "").strip()
            if not raw_shared_root:
                raise BrowserTtlConfigError("BUDDYSWITCH_SHARED_ROOT is required for browser TTL config")
            shared_root = Path(raw_shared_root)
    return Path(shared_root) / "config" / "browser.toml"


def _config_error(path: Path, message: str) -> BrowserTtlConfigError:
    return BrowserTtlConfigError(f"invalid browser TTL config {path}: {message}")


def _strict_integer(path: Path, ttl: dict[str, object], key: str, *, positive: bool) -> int:
    value = ttl.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _config_error(path, f"ttl.{key} must be an integer")
    if positive and value <= 0:
        raise _config_error(path, f"ttl.{key} must be greater than zero")
    if not positive and value < 0:
        raise _config_error(path, f"ttl.{key} must be zero or greater")
    return value


def load_browser_ttl_config(
    *,
    shared_root: Path | None = None,
    instance_root: Path | None = None,
) -> BrowserTtlConfig:
    path = browser_ttl_config_path(shared_root=shared_root, instance_root=instance_root)
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BrowserTtlConfigError(f"browser TTL config is missing: {path}") from exc
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise _config_error(path, str(exc)) from exc
    if not isinstance(payload, dict):
        raise _config_error(path, "root must be a table")
    unknown_top = set(payload) - TOP_LEVEL_KEYS
    if unknown_top:
        raise _config_error(path, f"unknown root keys: {', '.join(sorted(unknown_top))}")
    if set(payload) != TOP_LEVEL_KEYS:
        missing = TOP_LEVEL_KEYS - set(payload)
        raise _config_error(path, f"missing root keys: {', '.join(sorted(missing))}")
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != SCHEMA_VERSION:
        raise _config_error(path, f"schema_version must equal {SCHEMA_VERSION}")
    ttl = payload.get("ttl")
    if not isinstance(ttl, dict):
        raise _config_error(path, "ttl must be a table")
    unknown_ttl = set(ttl) - TTL_KEYS
    if unknown_ttl:
        raise _config_error(path, f"unknown ttl keys: {', '.join(sorted(unknown_ttl))}")
    missing_ttl = TTL_KEYS - set(ttl)
    if missing_ttl:
        raise _config_error(path, f"missing ttl keys: {', '.join(sorted(missing_ttl))}")
    return BrowserTtlConfig(
        page_idle_seconds=_strict_integer(path, ttl, "page_idle_seconds", positive=True),
        release_delay_seconds=_strict_integer(path, ttl, "release_delay_seconds", positive=False),
    )


def ensure_browser_ttl_config(*, shared_root: Path) -> Path:
    path = browser_ttl_config_path(shared_root=shared_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        load_browser_ttl_config(shared_root=shared_root)
        return path
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        os.chmod(temp_path, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(DEFAULT_CONFIG_TEXT)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError:
            pass
    finally:
        temp_path.unlink(missing_ok=True)
    load_browser_ttl_config(shared_root=shared_root)
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the host-global BuddySwitch browser TTL config.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ensure = subparsers.add_parser("ensure", help="Create defaults if absent and validate the config.")
    ensure.add_argument("--shared-root", required=True)
    return parser


def main(argv: list[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        path = ensure_browser_ttl_config(shared_root=Path(args.shared_root))
        config = load_browser_ttl_config(shared_root=Path(args.shared_root))
    except BrowserTtlConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "config_path": str(path),
                "page_idle_seconds": config.page_idle_seconds,
                "release_delay_seconds": config.release_delay_seconds,
                "schema_version": SCHEMA_VERSION,
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
        file=stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
