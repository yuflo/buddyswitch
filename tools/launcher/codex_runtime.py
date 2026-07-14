"""Resolve and validate the Codex runtime assigned to an actor instance."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


VERSION_TIMEOUT_SECONDS = 5.0
RUNTIME_RECORD_KEYS = frozenset({"executable", "version"})


class CodexRuntimeError(RuntimeError):
    """Raised when a Codex runtime cannot be resolved or validated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CodexRuntime:
    executable: Path
    version: str

    def to_record(self) -> dict[str, str]:
        return {
            "executable": str(self.executable),
            "version": self.version,
        }


def resolve_codex_runtime(candidate: str | None = None) -> CodexRuntime:
    if candidate is None:
        resolved_candidate = shutil.which("codex")
        if not resolved_candidate:
            raise CodexRuntimeError("RUNTIME_UNAVAILABLE", "Codex executable was not found on PATH.")
        path = Path(resolved_candidate)
    else:
        if not isinstance(candidate, str) or not candidate.strip():
            raise CodexRuntimeError("RUNTIME_UNAVAILABLE", "Codex executable is required.")
        path = Path(candidate.strip())
        if not path.is_absolute():
            raise CodexRuntimeError("RUNTIME_UNAVAILABLE", "Codex executable must be an absolute path.")

    executable = path.resolve(strict=False)
    _require_executable(executable, code="RUNTIME_UNAVAILABLE")
    version = _read_version(executable, code="RUNTIME_UNAVAILABLE")
    return CodexRuntime(executable=executable, version=version)


def runtime_from_instance(payload: Mapping[str, object]) -> CodexRuntime:
    raw_runtime = payload.get("codex_runtime")
    if not isinstance(raw_runtime, Mapping) or set(raw_runtime) != RUNTIME_RECORD_KEYS:
        raise CodexRuntimeError("INVALID_RUNTIME_RECORD", "Actor has no valid Codex runtime descriptor.")
    executable_value = raw_runtime.get("executable")
    version_value = raw_runtime.get("version")
    if not isinstance(executable_value, str) or not executable_value.strip():
        raise CodexRuntimeError("INVALID_RUNTIME_RECORD", "Codex runtime executable must be an absolute path.")
    executable = Path(executable_value.strip())
    if not executable.is_absolute():
        raise CodexRuntimeError("INVALID_RUNTIME_RECORD", "Codex runtime executable must be an absolute path.")
    if not isinstance(version_value, str) or not version_value.strip():
        raise CodexRuntimeError("INVALID_RUNTIME_RECORD", "Codex runtime version is required.")
    return CodexRuntime(executable=executable, version=version_value.strip())


def validate_codex_runtime(runtime: CodexRuntime) -> CodexRuntime:
    try:
        _require_executable(runtime.executable, code="RUNTIME_MISMATCH")
        actual_version = _read_version(runtime.executable, code="RUNTIME_MISMATCH")
    except CodexRuntimeError as exc:
        if exc.code == "RUNTIME_MISMATCH":
            raise
        raise CodexRuntimeError("RUNTIME_MISMATCH", str(exc)) from exc
    if actual_version != runtime.version:
        raise CodexRuntimeError(
            "RUNTIME_MISMATCH",
            f"Codex runtime version mismatch: expected {runtime.version}, got {actual_version}.",
        )
    return runtime


def _require_executable(executable: Path, *, code: str) -> None:
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise CodexRuntimeError(code, f"Codex executable is unavailable: {executable}")


def _read_version(executable: Path, *, code: str) -> str:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CodexRuntimeError(code, f"Codex version probe failed: {executable}") from exc
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        detail = completed.stderr.strip() or "empty version output"
        raise CodexRuntimeError(code, f"Codex version probe failed for {executable}: {detail}")
    return version
