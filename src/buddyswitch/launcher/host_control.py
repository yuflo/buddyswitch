"""Private Host Control facade for BuddySwitch instance lifecycle operations."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from buddyswitch.foundation.process_runtime.invocation import current_runtime_identity
from buddyswitch.runtime_support import env_manifest

HELPER_DIR = Path(__file__).resolve().parent
SHELL_ROOT = HELPER_DIR / "shell"

try:  # pragma: no cover - import mode depends on caller
    from . import actor_capability, codex_runtime, runtime_lock
except ImportError:  # pragma: no cover
    from buddyswitch.launcher import actor_capability  # type: ignore[no-redef]
    from buddyswitch.launcher import codex_runtime  # type: ignore[no-redef]
    from buddyswitch.launcher import runtime_lock  # type: ignore[no-redef]


VALID_ACTOR_ID_RE = re.compile(r"^act-[A-Za-z0-9._-]+$")
VALID_ROLE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SCRIPT_OPERATIONS = {
    "roles",
    "start",
    "list",
    "status",
    "clear",
    "resume",
    "stop",
    "delete",
    "interrupt",
    "compact",
}
LOCKED_OPERATIONS = SCRIPT_OPERATIONS - {"roles", "list", "status"}


class HostControlError(RuntimeError):
    """Raised when Host Control input, execution, or output is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        returncode: int = 1,
        timed_out: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.returncode = returncode
        self.timed_out = timed_out


@dataclass(frozen=True)
class _HostControlScriptRunner:
    shell_root: Path = SHELL_ROOT

    def run(self, operation: str, args: list[str], *, timeout_seconds: float) -> dict[str, object]:
        if operation not in SCRIPT_OPERATIONS:
            raise HostControlError("INVALID_REQUEST", f"Unknown host control operation: {operation}", returncode=2)
        script = self.shell_root / "host_control.sh"
        command = [str(script), operation, *args]
        try:
            environment = os.environ.copy()
            if operation in LOCKED_OPERATIONS:
                shared_root = _shared_root_from_environment()
                with runtime_lock.hold_runtime_lock(
                    str(shared_root),
                    runtime_lock.resolve_timeout(None),
                ):
                    completed = subprocess.run(
                        command,
                        cwd=self.shell_root,
                        env=environment,
                        text=True,
                        capture_output=True,
                        check=False,
                        timeout=timeout_seconds,
                    )
            else:
                completed = subprocess.run(
                    command,
                    cwd=self.shell_root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=timeout_seconds,
                )
        except subprocess.TimeoutExpired as exc:
            raise HostControlError(
                "COMMAND_TIMEOUT",
                f"Host control timed out: {operation}",
                returncode=1,
                timed_out=True,
            ) from exc
        except runtime_lock.RuntimeLockBusyError as exc:
            raise HostControlError(
                "LOCK_BUSY",
                str(exc),
                returncode=4,
            ) from exc

        payload = _load_json_object(completed.stdout)
        if completed.returncode != 0:
            raise _error_from_payload(
                payload,
                returncode=int(completed.returncode),
                fallback_message=_first_nonempty_line(completed.stderr)
                or _first_nonempty_line(completed.stdout)
                or f"Host control failed: {operation}",
            )
        if "error" in payload:
            raise _error_from_payload(payload, returncode=1, fallback_message=f"Host control failed: {operation}")
        return payload


class HostControl:
    def __init__(
        self,
        *,
        runner: _HostControlScriptRunner | Any | None = None,
        runtime_resolver: Callable[[], codex_runtime.CodexRuntime] | None = None,
    ) -> None:
        self._runner = runner or _HostControlScriptRunner()
        self._runtime_resolver = runtime_resolver or self._resolve_runtime

    def roles(self) -> list[dict[str, object]]:
        try:
            manifest = env_manifest.load_manifest()
        except env_manifest.ManifestError as exc:
            raise HostControlError("COMMAND_FAILED", str(exc), returncode=1) from exc
        return [
            {
                "id": role["id"],
                "label": role["label"],
                "scope": role["scope"],
            }
            for role in manifest["roles"]
        ]

    def allocate_actor_id(self, role_id: str) -> str:
        role = validate_role_id(role_id)
        return f"act-{role}-{uuid4().hex[:12]}"

    def start(self, role_id: str, actor_id: str | None = None) -> dict[str, object]:
        role = validate_role_id(role_id)
        try:
            env_manifest.require_role(env_manifest.load_manifest(), role)
        except env_manifest.ManifestError as exc:
            raise HostControlError("INVALID_REQUEST", str(exc), returncode=2) from exc
        requested_actor_id = self.allocate_actor_id(role) if actor_id is None else validate_actor_id(actor_id)
        try:
            runtime = self._runtime_resolver()
        except codex_runtime.CodexRuntimeError as exc:
            raise HostControlError(exc.code, str(exc), returncode=5) from exc
        payload = self._run(
            "start",
            [role, str(runtime.executable), runtime.version, requested_actor_id],
            timeout_seconds=120,
        )
        _require_str_fields(payload, "start", ("actor_id", "role", "workspace_dir", "project_workspace_dir", "instance_record"))
        if payload["actor_id"] != requested_actor_id:
            raise HostControlError(
                "COMMAND_FAILED",
                f"Host Control start actor id mismatch: expected {requested_actor_id}, got {payload['actor_id']}.",
                returncode=1,
            )
        diagnostics = payload.get("diagnostics")
        if diagnostics is not None and (
            not isinstance(diagnostics, list) or not all(isinstance(item, str) for item in diagnostics)
        ):
            raise HostControlError("COMMAND_FAILED", "Invalid Host Control start payload: diagnostics must be a list of strings.", returncode=1)
        return payload

    def prepare_retry(self, actor_id: str) -> dict[str, object]:
        normalized, role = self._retryable_start_failure(actor_id)
        return {
            "actor_id": normalized,
            "replacement_actor_id": self.allocate_actor_id(role),
            "role": role,
        }

    def retry(self, actor_id: str, replacement_actor_id: str) -> dict[str, object]:
        normalized, role = self._retryable_start_failure(actor_id)
        replacement = validate_actor_id(replacement_actor_id)
        if replacement == normalized or not replacement.startswith(f"act-{role}-"):
            raise HostControlError(
                "INVALID_REQUEST",
                "Retry replacement actor id must be a fresh id for the failed actor role.",
                returncode=2,
            )

        self.delete(normalized)
        started = dict(self.start(role, actor_id=replacement))
        started["previous_actor_id"] = normalized
        return started

    def list_instances(self, role_id: str | None = None) -> list[dict[str, object]]:
        args: list[str] = []
        if role_id is not None:
            args.append(validate_role_id(role_id))
        payload = self._run("list", args, timeout_seconds=10)
        return _expect_instance_rows(payload)

    def status(self, actor_id: str) -> dict[str, object]:
        normalized = validate_actor_id(actor_id)
        self._recorded_runtime(normalized)
        payload = self._run("status", [normalized], timeout_seconds=10)
        _require_str_fields(payload, "status", ("actor_id", "role", "status", "workspace_dir", "updated_at"))
        _require_nullable_str(payload, "status", "thread_id")
        _require_nullable_int(payload, "status", "browser_port")
        _require_nullable_dict(payload, "status", "codex_runtime")
        _require_nullable_dict(payload, "status", "last_failure")
        _require_dict_fields(payload, "status", ("app_server", "daemon", "runtime_broker", "thread"))
        return payload

    def clear(self, actor_id: str) -> dict[str, object]:
        payload = self._run("clear", [validate_actor_id(actor_id)], timeout_seconds=60)
        _require_str_fields(payload, "clear", ("actor_id", "previous_thread_id", "thread_id"))
        return payload

    def resume(self, actor_id: str) -> dict[str, object]:
        normalized = validate_actor_id(actor_id)
        runtime = self._recorded_runtime(normalized)
        payload = self._run(
            "resume",
            [normalized, str(runtime.executable), runtime.version],
            timeout_seconds=60,
        )
        _require_str_fields(payload, "resume", ("actor_id", "thread_id", "status"))
        return payload

    def stop(self, actor_id: str) -> dict[str, object]:
        payload = self._run("stop", [validate_actor_id(actor_id)], timeout_seconds=60)
        _require_str_fields(payload, "stop", ("actor_id", "status"))
        return payload

    def delete(self, actor_id: str) -> dict[str, object]:
        payload = self._run("delete", [validate_actor_id(actor_id)], timeout_seconds=60)
        _require_str_fields(payload, "delete", ("actor_id",))
        _require_bool(payload, "delete", "deleted")
        return payload

    def interrupt(self, actor_id: str) -> dict[str, object]:
        payload = self._run("interrupt", [validate_actor_id(actor_id)], timeout_seconds=30)
        _require_str_fields(payload, "interrupt", ("actor_id", "thread_id"))
        _require_nullable_str(payload, "interrupt", "turn_id")
        return payload

    def compact(self, actor_id: str) -> dict[str, object]:
        payload = self._run("compact", [validate_actor_id(actor_id)], timeout_seconds=30)
        _require_str_fields(payload, "compact", ("actor_id", "thread_id"))
        _require_bool(payload, "compact", "started")
        return payload

    def capabilities_get(self, actor_id: str) -> dict[str, object]:
        normalized = validate_actor_id(actor_id)
        instance_json = self._instance_json_for_actor(normalized)
        try:
            capabilities = actor_capability.describe_actor_capabilities(
                actor_capability.load_actor_capabilities(instance_json)
            )
        except actor_capability.ActorCapabilityError as exc:
            raise HostControlError("CAPABILITY_CONFIG_INVALID", str(exc), returncode=3) from exc
        return {"ok": True, "actor_id": normalized, "capabilities": capabilities}

    def capabilities_set(self, actor_id: str, parent: str, side: str) -> dict[str, object]:
        normalized = validate_actor_id(actor_id)
        instance_json = self._instance_json_for_actor(normalized)
        try:
            config = actor_capability.replace_actor_capabilities(
                instance_json,
                parent_level=parent,
                side_level=side,
            )
        except actor_capability.ActorCapabilityError as exc:
            message = str(exc)
            code = "CAPABILITY_CONFIG_WRITE_FAILED" if "failed to write capability config" in message else "INVALID_REQUEST"
            raise HostControlError(code, message, returncode=2) from exc
        return {
            "ok": True,
            "actor_id": normalized,
            "capabilities": actor_capability.describe_actor_capabilities(config),
        }

    def _run(self, operation: str, args: list[str], *, timeout_seconds: float) -> dict[str, object]:
        return self._runner.run(operation, args, timeout_seconds=timeout_seconds)

    def _retryable_start_failure(self, actor_id: str) -> tuple[str, str]:
        normalized = validate_actor_id(actor_id)
        instance = self.status(normalized)
        if instance["status"] != "inactive" or not isinstance(instance["last_failure"], dict):
            raise HostControlError(
                "LIFECYCLE_BLOCKED",
                f"Retry requires an inactive actor with a recorded start failure: {normalized}.",
                returncode=3,
            )
        try:
            role = validate_role_id(instance["role"])  # type: ignore[arg-type]
        except HostControlError as exc:
            raise HostControlError(
                "COMMAND_FAILED",
                "Invalid Host Control status payload: role must be a valid role id.",
                returncode=1,
            ) from exc
        return normalized, role

    @staticmethod
    def _resolve_runtime() -> codex_runtime.CodexRuntime:
        candidate = os.environ.get("BUDDYSWITCH_CODEX_BIN")
        return codex_runtime.resolve_codex_runtime(candidate)

    def _shared_root(self) -> Path:
        return _shared_root_from_environment()

    def _instance_json_for_actor(self, actor_id: str) -> Path:
        shared_root = self._shared_root()
        instances_root = (shared_root / "instances").resolve(strict=False)
        instance_json = (instances_root / actor_id / "instance.json").resolve(strict=False)
        try:
            instance_json.relative_to(instances_root)
        except ValueError as exc:
            raise HostControlError("INVALID_REQUEST", "Invalid actor instance path.", returncode=2) from exc
        if not instance_json.is_file():
            raise HostControlError("NOT_FOUND", f"actor instance not found: {actor_id}", returncode=1)
        return instance_json

    def _recorded_runtime(self, actor_id: str) -> codex_runtime.CodexRuntime:
        instance_json = self._instance_json_for_actor(actor_id)
        try:
            payload = json.loads(instance_json.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("record must be an object")
            expected_runtime = current_runtime_identity().to_record()
            if payload.get("runtime_identity") != expected_runtime:
                raise ValueError(
                    "recorded BuddySwitch runtime identity does not match the activated runtime"
                )
            runtime = codex_runtime.runtime_from_instance(payload)
            return codex_runtime.validate_codex_runtime(runtime)
        except (OSError, json.JSONDecodeError, ValueError, codex_runtime.CodexRuntimeError) as exc:
            raise HostControlError(
                "RUNTIME_MISMATCH",
                f"Actor Codex runtime is invalid for {actor_id}: {exc}. Stop/delete and recreate the instance.",
                returncode=5,
            ) from exc


def validate_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not VALID_ACTOR_ID_RE.fullmatch(actor_id):
        raise HostControlError("INVALID_REQUEST", "Invalid actor id.", returncode=2)
    return actor_id


def _shared_root_from_environment() -> Path:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        return Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
    source_home = os.environ.get("BUDDYSWITCH_SOURCE_HOME") or os.environ.get("HOME")
    if isinstance(source_home, str) and source_home.strip():
        return (
            Path(source_home.strip()).expanduser() / ".codex-buddyswitch"
        ).resolve(strict=False)
    return (Path.home() / ".codex-buddyswitch").resolve(strict=False)


def validate_role_id(role_id: str) -> str:
    if not isinstance(role_id, str) or role_id.startswith("-") or not VALID_ROLE_ID_RE.fullmatch(role_id):
        raise HostControlError("INVALID_REQUEST", "Invalid role id.", returncode=2)
    return role_id


def _require_str_fields(payload: dict[str, object], operation: str, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value:
            raise HostControlError(
                "COMMAND_FAILED",
                f"Invalid Host Control {operation} payload: {field_name} must be a non-empty string.",
                returncode=1,
            )


def _require_dict_fields(payload: dict[str, object], operation: str, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if not isinstance(payload.get(field_name), dict):
            raise HostControlError(
                "COMMAND_FAILED",
                f"Invalid Host Control {operation} payload: {field_name} must be an object.",
                returncode=1,
            )


def _require_bool(payload: dict[str, object], operation: str, field_name: str) -> None:
    if not isinstance(payload.get(field_name), bool):
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be a boolean.",
            returncode=1,
        )


def _require_nullable_str(payload: dict[str, object], operation: str, field_name: str) -> None:
    if field_name not in payload or (payload[field_name] is not None and not isinstance(payload[field_name], str)):
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be a string or null.",
            returncode=1,
        )


def _require_nullable_int(payload: dict[str, object], operation: str, field_name: str) -> None:
    value = payload.get(field_name)
    if field_name not in payload or (value is not None and (not isinstance(value, int) or isinstance(value, bool))):
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be an integer or null.",
            returncode=1,
        )


def _require_nullable_dict(payload: dict[str, object], operation: str, field_name: str) -> None:
    if field_name not in payload or (payload[field_name] is not None and not isinstance(payload[field_name], dict)):
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be an object or null.",
            returncode=1,
        )


def _load_json_object(stdout: str) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HostControlError("COMMAND_FAILED", "Host control returned invalid JSON.", returncode=1) from exc
    if not isinstance(payload, dict):
        raise HostControlError("COMMAND_FAILED", "Host control JSON must be an object.", returncode=1)
    return payload


def _error_from_payload(payload: dict[str, object], *, returncode: int, fallback_message: str) -> HostControlError:
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
        if isinstance(code, str) and code and isinstance(message, str) and message:
            return HostControlError(code, message, returncode=returncode)
    return HostControlError(_code_for_returncode(returncode), fallback_message, returncode=returncode)


def _code_for_returncode(returncode: int) -> str:
    if returncode == 2:
        return "INVALID_REQUEST"
    if returncode == 3:
        return "LIFECYCLE_BLOCKED"
    if returncode == 4:
        return "LOCK_BUSY"
    return "COMMAND_FAILED"


def _expect_object_list(payload: dict[str, object], field_name: str) -> list[dict[str, object]]:
    rows = payload.get(field_name)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise HostControlError("COMMAND_FAILED", f"Invalid Host Control {field_name} payload.", returncode=1)
    return [dict(row) for row in rows]


def _expect_role_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = _expect_object_list(payload, "roles")
    for row in rows:
        _require_str_fields(row, "roles row", ("id", "label", "scope"))
    return rows


def _expect_instance_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = _expect_object_list(payload, "instances")
    for row in rows:
        _require_str_fields(
            row,
            "instances row",
            ("actor_id", "role", "status", "app_server_health", "updated_at", "workspace_dir"),
        )
        _require_valid_actor_id_field(row, "instances row", "actor_id")
        _require_valid_role_id_field(row, "instances row", "role")
        _require_nullable_str(row, "instances row", "thread_id")
        _require_nullable_int(row, "instances row", "browser_port")
        _require_nullable_dict(row, "instances row", "last_failure")
    return rows


def _require_valid_actor_id_field(payload: dict[str, object], operation: str, field_name: str) -> None:
    try:
        validate_actor_id(payload[field_name])  # type: ignore[arg-type]
    except HostControlError as exc:
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be a valid actor id.",
            returncode=1,
        ) from exc


def _require_valid_role_id_field(payload: dict[str, object], operation: str, field_name: str) -> None:
    try:
        validate_role_id(payload[field_name])  # type: ignore[arg-type]
    except HostControlError as exc:
        raise HostControlError(
            "COMMAND_FAILED",
            f"Invalid Host Control {operation} payload: {field_name} must be a valid role id.",
            returncode=1,
        ) from exc


def _first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None
