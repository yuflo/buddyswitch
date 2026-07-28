"""Fail-closed activation for one non-editable BuddySwitch installation."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Sequence


PACKAGE_NAME = "buddyswitch"
ACTIVATION_SCHEMA_VERSION = 1
ACTIVATION_FILE = "activation.json"
RUNTIME_ENV = "BUDDYSWITCH_RUNTIME_DIR"
UNAVAILABLE_EXIT = 5
MISMATCH_EXIT = 6
NON_RUNTIME_PACKAGE_DIRS = frozenset({"tests", "__pycache__"})
RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "source_root",
        "source_digest",
        "package_version",
        "distribution_digest",
        "python_executable",
        "package_root",
        "activated_at",
    }
)


class RuntimeActivationError(RuntimeError):
    """Stable failure raised before any BuddySwitch lifecycle mutation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = dict(details or {})


def _absolute_executable() -> Path:
    return Path(os.path.abspath(sys.executable))


def runtime_dir() -> Path:
    configured = os.environ.get(RUNTIME_ENV)
    if configured is not None:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            raise RuntimeActivationError(
                "RUNTIME_UNAVAILABLE",
                f"{RUNTIME_ENV} must be an absolute path",
                exit_code=UNAVAILABLE_EXIT,
            )
        return candidate.resolve(strict=False)
    executable = _absolute_executable()
    if executable.parent.name != "bin" or executable.parent.parent.name != "venv":
        raise RuntimeActivationError(
            "RUNTIME_UNAVAILABLE",
            f"{RUNTIME_ENV} is unset and Python is not runtime/venv/bin/python",
            exit_code=UNAVAILABLE_EXIT,
        )
    return executable.parent.parent.parent.resolve(strict=False)


def activation_path() -> Path:
    return runtime_dir() / ACTIVATION_FILE


def _expected_runtime_python(chosen_runtime_dir: Path) -> Path:
    return (chosen_runtime_dir / "venv" / "bin" / "python").absolute()


def _require_runtime_interpreter(chosen_runtime_dir: Path) -> Path:
    expected = _expected_runtime_python(chosen_runtime_dir)
    actual = _absolute_executable()
    if not expected.is_file():
        raise RuntimeActivationError(
            "RUNTIME_UNAVAILABLE",
            f"runtime Python is missing: {expected}",
            exit_code=UNAVAILABLE_EXIT,
        )
    if actual != expected:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "active Python does not match runtime/venv/bin/python",
            exit_code=MISMATCH_EXIT,
            details={"expected": str(expected), "actual": str(actual)},
        )
    return actual


def _reject_tree_symlinks(root: Path, *, label: str) -> None:
    for current_text, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        for name in (*directory_names, *file_names):
            candidate = current / name
            if candidate.is_symlink():
                raise RuntimeActivationError(
                    "RUNTIME_MISMATCH",
                    f"{label} symlink is forbidden: {candidate}",
                    exit_code=MISMATCH_EXIT,
                    details={"path": str(candidate)},
                )


def _source_package_manifest(source_root: Path) -> dict[str, bytes]:
    package_source = source_root / "src" / PACKAGE_NAME
    if package_source.is_symlink() or not package_source.is_dir():
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "source root must contain a real src/buddyswitch directory",
            exit_code=MISMATCH_EXIT,
        )
    _reject_tree_symlinks(package_source, label="package source")

    manifest: dict[str, bytes] = {}
    for current_text, directory_names, file_names in os.walk(
        package_source,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        directory_names[:] = [
            name
            for name in directory_names
            if name not in NON_RUNTIME_PACKAGE_DIRS
        ]
        for name in file_names:
            candidate = current / name
            if candidate.suffix == ".pyc":
                continue
            manifest[candidate.relative_to(package_source).as_posix()] = (
                candidate.read_bytes()
            )
    return manifest


def _content_digest(entries: Sequence[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative_text, content in sorted(entries):
        relative = relative_text.encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _source_digest(
    source_root: Path,
    package_manifest: dict[str, bytes],
) -> str:
    pyproject = source_root / "pyproject.toml"
    if pyproject.is_symlink() or not pyproject.is_file():
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "source root must contain a real pyproject.toml file",
            exit_code=MISMATCH_EXIT,
        )
    entries = [("pyproject.toml", pyproject.read_bytes())]
    entries.extend(
        (f"src/{PACKAGE_NAME}/{relative}", content)
        for relative, content in package_manifest.items()
    )
    return _content_digest(entries)


def _package_root() -> Path:
    import buddyswitch

    module_file = getattr(buddyswitch, "__file__", None)
    if not isinstance(module_file, str):
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed buddyswitch package has no concrete module file",
            exit_code=MISMATCH_EXIT,
        )
    module_path = Path(module_file)
    package_root = module_path.parent
    if (
        module_path.is_symlink()
        or package_root.is_symlink()
        or not package_root.is_dir()
    ):
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed buddyswitch package must use a real package directory",
            exit_code=MISMATCH_EXIT,
        )
    return package_root.absolute()


def _distribution_manifest() -> tuple[str, str, Path, dict[str, bytes]]:
    try:
        distribution = importlib.metadata.distribution(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeActivationError(
            "RUNTIME_UNAVAILABLE",
            "installed buddyswitch distribution is missing",
            exit_code=UNAVAILABLE_EXIT,
        ) from exc

    direct_url_text = distribution.read_text("direct_url.json")
    if direct_url_text:
        try:
            direct_url = json.loads(direct_url_text)
        except json.JSONDecodeError as exc:
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                "installed distribution direct_url.json is invalid",
                exit_code=MISMATCH_EXIT,
            ) from exc
        if (
            isinstance(direct_url, dict)
            and isinstance(direct_url.get("dir_info"), dict)
            and direct_url["dir_info"].get("editable") is True
        ):
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                "editable BuddySwitch installations are forbidden",
                exit_code=MISMATCH_EXIT,
            )

    package_root = _package_root()
    _reject_tree_symlinks(package_root, label="installed package")
    record_text = distribution.read_text("RECORD")
    if not record_text:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed distribution manifest is empty",
            exit_code=MISMATCH_EXIT,
        )
    try:
        record_rows = list(csv.reader(record_text.splitlines()))
    except csv.Error as exc:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed distribution RECORD is invalid",
            exit_code=MISMATCH_EXIT,
        ) from exc

    distribution_entries: list[tuple[str, bytes]] = []
    installed_manifest: dict[str, bytes] = {}
    recorded_package_files: set[str] = set()
    for row in record_rows:
        if len(row) != 3 or not row[0]:
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                "installed distribution RECORD is invalid",
                exit_code=MISMATCH_EXIT,
            )
        relative = row[0]
        package_path = Path(relative)
        if "__pycache__" in package_path.parts or relative.endswith(".pyc"):
            continue
        installed_path = Path(distribution.locate_file(package_path))
        is_package_file = bool(
            package_path.parts and package_path.parts[0] == PACKAGE_NAME
        )
        if is_package_file and installed_path.is_symlink():
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                f"installed package file is a symlink: {relative}",
                exit_code=MISMATCH_EXIT,
                details={"path": relative},
            )
        if not installed_path.is_file():
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                f"installed distribution file is missing: {relative}",
                exit_code=MISMATCH_EXIT,
                details={"path": relative},
            )
        content = installed_path.read_bytes()
        distribution_entries.append((relative, content))
        if is_package_file:
            package_relative = Path(*package_path.parts[1:]).as_posix()
            expected_path = package_root / package_relative
            if installed_path.absolute() != expected_path.absolute():
                raise RuntimeActivationError(
                    "RUNTIME_MISMATCH",
                    f"installed package path disagrees with RECORD: {relative}",
                    exit_code=MISMATCH_EXIT,
                    details={"path": relative},
                )
            if package_relative in installed_manifest:
                raise RuntimeActivationError(
                    "RUNTIME_MISMATCH",
                    f"installed package path is recorded more than once: {relative}",
                    exit_code=MISMATCH_EXIT,
                    details={"path": relative},
                )
            installed_manifest[package_relative] = content
            recorded_package_files.add(package_relative)

    actual_package_files: dict[str, Path] = {}
    for current_text, directory_names, file_names in os.walk(
        package_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        directory_names[:] = [
            name for name in directory_names if name != "__pycache__"
        ]
        for name in file_names:
            candidate = current / name
            if candidate.suffix == ".pyc":
                continue
            actual_package_files[
                candidate.relative_to(package_root).as_posix()
            ] = candidate

    unrecorded = sorted(set(actual_package_files) - recorded_package_files)
    if unrecorded:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed package contains files outside its distribution manifest",
            exit_code=MISMATCH_EXIT,
            details={
                "paths": [str(actual_package_files[relative]) for relative in unrecorded]
            },
        )

    return (
        distribution.version,
        _content_digest(distribution_entries),
        package_root,
        installed_manifest,
    )


def _require_package_correspondence(
    source: dict[str, bytes],
    installed: dict[str, bytes],
) -> None:
    source_only = sorted(set(source) - set(installed))
    installed_only = sorted(set(installed) - set(source))
    changed = sorted(
        relative
        for relative in set(source) & set(installed)
        if source[relative] != installed[relative]
    )
    if source_only or installed_only or changed:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "source and installed BuddySwitch package content disagree",
            exit_code=MISMATCH_EXIT,
            details={
                "source_only": source_only,
                "installed_only": installed_only,
                "changed": changed,
            },
        )


def _read_record(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeActivationError(
            "RUNTIME_UNAVAILABLE",
            f"activation record is missing: {path}",
            exit_code=UNAVAILABLE_EXIT,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            f"activation record is unreadable: {exc}",
            exit_code=MISMATCH_EXIT,
        ) from exc
    if not isinstance(payload, dict) or set(payload) != RECORD_FIELDS:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "activation record has an unsupported schema",
            exit_code=MISMATCH_EXIT,
        )
    if payload.get("schema_version") != ACTIVATION_SCHEMA_VERSION:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "activation record schema version does not match",
            exit_code=MISMATCH_EXIT,
        )
    for field in RECORD_FIELDS - {"schema_version"}:
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                f"activation record field must be non-empty text: {field}",
                exit_code=MISMATCH_EXIT,
            )
    return payload


def _atomic_write_record(path: Path, record: dict[str, Any]) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise RuntimeActivationError(
            "RUNTIME_UNAVAILABLE",
            f"runtime directory is missing: {parent}",
            exit_code=UNAVAILABLE_EXIT,
        )
    if path.exists() and path.is_symlink():
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            f"activation record must not be a symlink: {path}",
            exit_code=MISMATCH_EXIT,
        )
    temporary_path: Path | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".activation.",
            suffix=".tmp",
            dir=parent,
        )
        temporary_path = Path(temporary)
        os.fchmod(descriptor, 0o600)
        payload = (
            json.dumps(record, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def activate(source_root: Path) -> dict[str, Any]:
    chosen_runtime_dir = runtime_dir()
    python_executable = _require_runtime_interpreter(chosen_runtime_dir)
    normalized_source = source_root.expanduser().resolve(strict=True)
    source_manifest = _source_package_manifest(normalized_source)
    (
        version,
        distribution_digest,
        package_root,
        installed_manifest,
    ) = _distribution_manifest()
    if package_root.is_relative_to(normalized_source / "src"):
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "BuddySwitch resolves from source instead of the installed distribution",
            exit_code=MISMATCH_EXIT,
        )
    _require_package_correspondence(source_manifest, installed_manifest)
    record = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "source_root": str(normalized_source),
        "source_digest": _source_digest(normalized_source, source_manifest),
        "package_version": version,
        "distribution_digest": distribution_digest,
        "python_executable": str(python_executable),
        "package_root": str(package_root),
        "activated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    _atomic_write_record(chosen_runtime_dir / ACTIVATION_FILE, record)
    return record


def verify_installed(
    *,
    expected_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chosen_runtime_dir = runtime_dir()
    python_executable = _require_runtime_interpreter(chosen_runtime_dir)
    path = chosen_runtime_dir / ACTIVATION_FILE
    record = _read_record(path)

    if expected_record is not None and expected_record != record:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "published BuddySwitch runtime identity does not match activation",
            exit_code=MISMATCH_EXIT,
        )

    comparisons: dict[str, tuple[str, str]] = {}
    comparisons["python_executable"] = (
        str(record["python_executable"]),
        str(python_executable),
    )
    (
        version,
        distribution_digest,
        package_root,
        _installed_manifest,
    ) = _distribution_manifest()
    comparisons["package_version"] = (str(record["package_version"]), version)
    comparisons["distribution_digest"] = (
        str(record["distribution_digest"]),
        distribution_digest,
    )
    comparisons["package_root"] = (
        str(record["package_root"]),
        str(package_root),
    )
    mismatches = {
        field: {"recorded": expected, "actual": actual}
        for field, (expected, actual) in comparisons.items()
        if expected != actual
    }
    if mismatches:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed BuddySwitch runtime identity does not match activation",
            exit_code=MISMATCH_EXIT,
            details={"mismatches": mismatches},
        )
    return record


def verify() -> dict[str, Any]:
    record = verify_installed()
    source_root = Path(record["source_root"]).expanduser().resolve(strict=False)
    source_manifest = _source_package_manifest(source_root)
    _, _, _, installed_manifest = _distribution_manifest()
    _require_package_correspondence(source_manifest, installed_manifest)

    mismatches: dict[str, dict[str, str]] = {}
    if str(record["source_root"]) != str(source_root):
        mismatches["source_root"] = {
            "recorded": str(record["source_root"]),
            "actual": str(source_root),
        }
    actual_source_digest = _source_digest(source_root, source_manifest)
    if str(record["source_digest"]) != actual_source_digest:
        mismatches["source_digest"] = {
            "recorded": str(record["source_digest"]),
            "actual": actual_source_digest,
        }
    if mismatches:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "installed BuddySwitch runtime identity does not match activation",
            exit_code=MISMATCH_EXIT,
            details={"mismatches": mismatches},
        )
    return record


def _success(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": kind,
        "data": {"runtime_identity": record},
    }


def _failure(error: RuntimeActivationError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddyswitch-runtime-activation")
    commands = parser.add_subparsers(dest="command", required=True)
    activate_parser = commands.add_parser("activate")
    activate_parser.add_argument("--source-root", required=True)
    commands.add_parser("verify")
    commands.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "activate":
            record = activate(Path(arguments.source_root))
            payload = _success("runtime.activate", record)
        elif arguments.command == "verify":
            payload = _success("runtime.verify", verify())
        else:
            payload = _success("runtime.status", verify())
    except RuntimeActivationError as exc:
        print(json.dumps(_failure(exc), ensure_ascii=True, sort_keys=True))
        return exc.exit_code
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0
