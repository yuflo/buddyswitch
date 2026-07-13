"""Actor session input and attach boundary."""

import json
import os
import re
import shlex
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_capability  # noqa: E402
import app_server  # noqa: E402


VALID_ACTOR_ID_RE = re.compile(r"^act-[A-Za-z0-9._-]+$")
DEFAULT_PERMISSIONS = "buddyswitch-runtime"


class ActorSessionError(RuntimeError):
    """Raised when actor session input or attach cannot be resolved."""


@dataclass(frozen=True)
class AttachDescriptor:
    actor_id: str
    thread_id: str
    cwd: Path
    argv: tuple[str, ...]
    env: Mapping[str, str]


@dataclass(frozen=True)
class _ActorContext:
    actor_id: str
    role: str
    thread_id: str
    socket_path: Path
    instance_json: Path
    instance_root: Path
    workspace_dir: Path
    project_workspace_dir: Path


def input_actor_turn(
    *,
    socket_path: Path,
    instance_json: Path,
    thread_id: str,
    text: str,
    permissions: str,
) -> dict[str, object]:
    normalized_text = _require_text(text, "input text")
    normalized_thread_id = _require_text(thread_id, "thread id")
    normalized_permissions = _require_text(permissions, "permissions")
    try:
        resolved = actor_capability.resolve_parent_capability(instance_json)
    except actor_capability.ActorCapabilityError as exc:
        raise ActorSessionError(f"parent capability invalid: {exc}") from exc

    try:
        app_server.thread_settings_update(
            socket_path,
            normalized_thread_id,
            model=resolved.model,
            effort=resolved.effort,
        )
    except app_server.AppServerError as exc:
        raise ActorSessionError(f"parent settings update failed: {exc}") from exc

    try:
        return app_server.input_turn(
            socket_path,
            normalized_thread_id,
            normalized_text,
            normalized_permissions,
        )
    except app_server.AppServerError as exc:
        raise ActorSessionError(f"input turn failed: {exc}") from exc


class ActorSession:
    def __init__(self, *, shared_root: Path, repo_root: Path, codex_bin: str = "codex") -> None:
        self._shared_root = Path(shared_root).expanduser().resolve(strict=False)
        self._repo_root = Path(repo_root).expanduser().resolve(strict=False)
        self._codex_bin = _require_text(codex_bin, "codex bin")

    def input(self, actor_id: str, text: str) -> dict[str, object]:
        context = self._context(actor_id)
        result = dict(
            input_actor_turn(
                socket_path=context.socket_path,
                instance_json=context.instance_json,
                thread_id=context.thread_id,
                text=text,
                permissions=DEFAULT_PERMISSIONS,
            )
        )
        result["actor_id"] = context.actor_id
        result["thread_id"] = context.thread_id
        return result

    def resolve_attach(self, actor_id: str) -> AttachDescriptor:
        context = self._context(actor_id)
        try:
            payload = app_server.thread_resume(
                context.socket_path,
                context.thread_id,
                workspace_dir=context.workspace_dir,
                shared_project_workspace_dir=context.project_workspace_dir,
                permissions=DEFAULT_PERMISSIONS,
            )
        except app_server.AppServerUnavailableError as exc:
            raise ActorSessionError(f"actor app server unhealthy for {context.actor_id}: {exc}") from exc
        except app_server.AppServerError as exc:
            raise ActorSessionError(f"thread/resume failed for {context.thread_id}: {exc}") from exc
        thread = payload.get("thread") if isinstance(payload, Mapping) else None
        resumed_thread_id = thread.get("id") if isinstance(thread, Mapping) else None
        if resumed_thread_id != context.thread_id:
            raise ActorSessionError(f"thread/resume returned unexpected thread id: {resumed_thread_id or ''}")
        env = _attach_env(context, repo_root=self._repo_root)
        argv = (
            self._codex_bin,
            "resume",
            "--remote",
            f"unix://{context.socket_path}",
            context.thread_id,
        )
        return AttachDescriptor(
            actor_id=context.actor_id,
            thread_id=context.thread_id,
            cwd=context.workspace_dir,
            argv=argv,
            env=env,
        )

    def exec_attach(self, actor_id: str) -> NoReturn:
        descriptor = self.resolve_attach(actor_id)
        previous_cwd = Path.cwd()
        try:
            os.chdir(descriptor.cwd)
            os.execvpe(descriptor.argv[0], descriptor.argv, dict(descriptor.env))
        finally:
            os.chdir(previous_cwd)
        raise AssertionError("os.execvpe returned")

    def _context(self, actor_id: str) -> _ActorContext:
        normalized_actor_id = _validate_actor_id(actor_id)
        instance_root = (self._shared_root / "instances" / normalized_actor_id).resolve(strict=False)
        instance_json = instance_root / "instance.json"
        if not instance_json.is_file():
            raise ActorSessionError(f"actor not found: {normalized_actor_id}")
        payload = _read_instance(instance_json)
        if payload.get("actor_id") != normalized_actor_id:
            raise ActorSessionError(f"actor record mismatch: {normalized_actor_id}")
        role = _require_text(payload.get("role"), "actor role")
        thread_id = _thread_id_from_record(payload)
        workspace_dir = instance_root / "workspace"
        _reject_mismatched_record_path(payload, "instance_root", instance_root, "instance root")
        _reject_mismatched_record_path(payload, "workspace_dir", workspace_dir, "workspace dir")
        project_workspace_dir = (self._shared_root / "project" / "workspace").resolve(strict=False)
        _reject_mismatched_record_path(payload, "project_workspace_dir", project_workspace_dir, "project workspace dir")
        socket_path = _path_value(payload.get("app_server_socket"), instance_root / "runtime" / "app-server.sock")
        return _ActorContext(
            actor_id=normalized_actor_id,
            role=role,
            thread_id=thread_id,
            socket_path=socket_path,
            instance_json=instance_json,
            instance_root=instance_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
        )


def terminal_command_from_descriptor(descriptor: AttachDescriptor) -> str:
    assignments = " ".join(
        f"{key}={shlex.quote(value)}"
        for key, value in sorted(descriptor.env.items())
        if key != "PATH"
    )
    path_prefix = f"PATH={shlex.quote(descriptor.env['PATH'])} " if descriptor.env.get("PATH") else ""
    command = " ".join(shlex.quote(part) for part in descriptor.argv)
    env_parts = f"{path_prefix}{assignments}".strip()
    env_command = f"env {env_parts} {command}" if env_parts else command
    return f"cd {shlex.quote(str(descriptor.cwd))} && {env_command}"


def _attach_env(context: _ActorContext, *, repo_root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if (
            key in {"PATH", "TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE", "BUDDYSWITCH_PYTHON"}
            or key.startswith("LC_")
            or key.startswith("BUDDYSWITCH_TEST_")
        ):
            env[key] = value
    env.update(
        {
            "HOME": str(context.instance_root / "home"),
            "CODEX_HOME": str(context.instance_root / "codex-home"),
            "XDG_CONFIG_HOME": str(context.instance_root / "xdg-config"),
            "BUDDYSWITCH_REPO_ROOT": str(repo_root),
            "BUDDYSWITCH_ACTOR_ID": context.actor_id,
            "BUDDYSWITCH_ROLE_ID": context.role,
            "BUDDYSWITCH_INSTANCE_JSON": str(context.instance_json),
            "BUDDYSWITCH_ACTOR_PRIVATE_DIR": str(context.workspace_dir / "private"),
            "BUDDYSWITCH_INSTANCE_TMP": str(context.instance_root / "tmp"),
            "BUDDYSWITCH_PROJECT_WORKSPACE_DIR": str(context.project_workspace_dir),
            "TMPDIR": str(context.instance_root / "tmp"),
            "TMP": str(context.instance_root / "tmp"),
            "TEMP": str(context.instance_root / "tmp"),
            "TMPPREFIX": str(context.instance_root / "tmp" / "zsh"),
        }
    )
    return env


def _read_instance(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ActorSessionError(f"invalid actor record JSON: {path}") from exc
    except OSError as exc:
        raise ActorSessionError(f"failed to read actor record: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ActorSessionError(f"actor record must be an object: {path}")
    return payload


def _validate_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not VALID_ACTOR_ID_RE.fullmatch(actor_id):
        raise ActorSessionError("invalid actor id")
    return actor_id


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActorSessionError(f"{label} is required")
    return value.strip()


def _thread_id_from_record(payload: Mapping[str, Any]) -> str:
    value = payload.get("thread_id")
    if not isinstance(value, str) or not value.strip():
        raise ActorSessionError("actor has no thread id; stop/delete and recreate the instance")
    return value.strip()


def _reject_mismatched_record_path(payload: Mapping[str, Any], key: str, expected: Path, label: str) -> None:
    value = payload.get(key)
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ActorSessionError(f"{label} in actor record must be a path")
    actual = Path(value.strip()).expanduser()
    if not actual.is_absolute() or actual.resolve(strict=False) != expected:
        raise ActorSessionError(f"{label} in actor record does not match actor directory")


def _path_value(value: Any, fallback: Path) -> Path:
    if isinstance(value, str) and value.strip():
        return Path(value.strip())
    return fallback
