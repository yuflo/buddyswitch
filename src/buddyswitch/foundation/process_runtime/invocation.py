"""Verified process invocation and immutable installed runtime identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
from typing import Callable

from buddyswitch.foundation.process_runtime.activation import (
    MISMATCH_EXIT,
    RuntimeActivationError,
    verify,
    verify_installed,
)


RUNTIME_IDENTITY_ENV = "BUDDYSWITCH_RUNTIME_IDENTITY"
PROJECT_SOURCE_ENV = "BUDDYSWITCH_PROJECT_SOURCE"
PACKAGE_ROOT_ENV = "BUDDYSWITCH_PACKAGE_ROOT"
RUNTIME_PYTHON_ENV = "BUDDYSWITCH_PYTHON"
SOURCE_ROOT_ENV = "BUDDYSWITCH_SOURCE_ROOT"


@dataclass(frozen=True)
class RuntimeIdentity:
    schema_version: int
    source_root: str
    source_digest: str
    package_version: str
    distribution_digest: str
    python_executable: str
    package_root: str
    activated_at: str

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "RuntimeIdentity":
        return cls(
            schema_version=int(record["schema_version"]),
            source_root=str(record["source_root"]),
            source_digest=str(record["source_digest"]),
            package_version=str(record["package_version"]),
            distribution_digest=str(record["distribution_digest"]),
            python_executable=str(record["python_executable"]),
            package_root=str(record["package_root"]),
            activated_at=str(record["activated_at"]),
        )

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    @property
    def project_source(self) -> Path:
        return Path(self.source_root) / "projects" / "app"


def current_runtime_identity() -> RuntimeIdentity:
    published = os.environ.get(RUNTIME_IDENTITY_ENV)
    if isinstance(published, str) and published.strip():
        try:
            payload = json.loads(published)
        except json.JSONDecodeError as exc:
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                "published BuddySwitch runtime identity is invalid JSON",
                exit_code=MISMATCH_EXIT,
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeActivationError(
                "RUNTIME_MISMATCH",
                "published BuddySwitch runtime identity must be an object",
                exit_code=MISMATCH_EXIT,
            )
        return RuntimeIdentity.from_record(
            verify_installed(expected_record=payload)
        )
    return RuntimeIdentity.from_record(verify())


def project_source() -> Path:
    configured = os.environ.get(PROJECT_SOURCE_ENV)
    if isinstance(configured, str) and configured.strip():
        return Path(configured.strip()).expanduser().resolve(strict=False)
    return current_runtime_identity().project_source.resolve(strict=False)


def publish_verified_environment(identity: RuntimeIdentity) -> None:
    record = identity.to_record()
    os.environ[RUNTIME_IDENTITY_ENV] = json.dumps(
        record,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    os.environ[PROJECT_SOURCE_ENV] = str(identity.project_source)
    os.environ[PACKAGE_ROOT_ENV] = identity.package_root
    os.environ[RUNTIME_PYTHON_ENV] = identity.python_executable
    os.environ[SOURCE_ROOT_ENV] = identity.source_root


def _failure(error: RuntimeActivationError) -> dict[str, object]:
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
    }


def run_verified(owner: Callable[[], int]) -> int:
    try:
        identity = current_runtime_identity()
    except RuntimeActivationError as exc:
        print(json.dumps(_failure(exc), ensure_ascii=True, sort_keys=True))
        return exc.exit_code
    if Path(sys.executable).absolute() != Path(identity.python_executable):
        error = RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "verified runtime Python changed before owner invocation",
            exit_code=6,
        )
        print(json.dumps(_failure(error), ensure_ascii=True, sort_keys=True))
        return error.exit_code
    publish_verified_environment(identity)
    return int(owner())
