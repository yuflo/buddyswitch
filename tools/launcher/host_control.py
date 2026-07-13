"""Private Host Control facade for BuddySwitch instance lifecycle operations."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


HELPER_DIR = Path(__file__).resolve().parent
SCRIPTS = HELPER_DIR.parents[1] / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:  # pragma: no cover - import mode depends on caller
    from . import actor_capability
except ImportError:  # pragma: no cover
    import actor_capability  # type: ignore[no-redef]


REPO_ROOT = HELPER_DIR.parents[1]
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
    repo_root: Path = REPO_ROOT

    def run(self, operation: str, args: list[str], *, timeout_seconds: float) -> dict[str, object]:
        if operation not in SCRIPT_OPERATIONS:
            raise HostControlError("INVALID_REQUEST", f"Unknown host control operation: {operation}", returncode=2)
        script = self.repo_root / "tools" / "launcher" / "host_control.sh"
        command = [str(script), operation, *args]
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
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
        repo_root: Path = REPO_ROOT,
        runner: _HostControlScriptRunner | Any | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._runner = runner or _HostControlScriptRunner(repo_root=repo_root)

    def roles(self) -> list[dict[str, object]]:
        payload = self._run("roles", [], timeout_seconds=10)
        return _expect_role_rows(payload)

    def start(self, role_id: str) -> dict[str, object]:
        role = validate_role_id(role_id)
        payload = self._run("start", [role], timeout_seconds=120)
        _require_str_fields(payload, "start", ("actor_id", "role", "workspace_dir", "project_workspace_dir", "instance_record"))
        diagnostics = payload.get("diagnostics")
        if diagnostics is not None and (
            not isinstance(diagnostics, list) or not all(isinstance(item, str) for item in diagnostics)
        ):
            raise HostControlError("COMMAND_FAILED", "Invalid Host Control start payload: diagnostics must be a list of strings.", returncode=1)
        return payload

    def list_instances(self, role_id: str | None = None) -> list[dict[str, object]]:
        args: list[str] = []
        if role_id is not None:
            args.append(validate_role_id(role_id))
        payload = self._run("list", args, timeout_seconds=10)
        return _expect_instance_rows(payload)

    def status(self, actor_id: str) -> dict[str, object]:
        payload = self._run("status", [validate_actor_id(actor_id)], timeout_seconds=10)
        _require_str_fields(payload, "status", ("actor_id", "role", "status", "workspace_dir", "updated_at"))
        _require_nullable_str(payload, "status", "thread_id")
        _require_nullable_int(payload, "status", "browser_port")
        _require_dict_fields(payload, "status", ("app_server", "daemon", "runtime_broker", "thread"))
        return payload

    def clear(self, actor_id: str) -> dict[str, object]:
        payload = self._run("clear", [validate_actor_id(actor_id)], timeout_seconds=60)
        _require_str_fields(payload, "clear", ("actor_id", "previous_thread_id", "thread_id"))
        return payload

    def resume(self, actor_id: str) -> dict[str, object]:
        payload = self._run("resume", [validate_actor_id(actor_id)], timeout_seconds=60)
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

    def _shared_root(self) -> Path:
        raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
        if isinstance(raw_shared_root, str) and raw_shared_root.strip():
            return Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
        source_home = os.environ.get("BUDDYSWITCH_SOURCE_HOME") or os.environ.get("HOME")
        if isinstance(source_home, str) and source_home.strip():
            return (Path(source_home.strip()).expanduser() / ".codex-buddyswitch").resolve(strict=False)
        return (Path.home() / ".codex-buddyswitch").resolve(strict=False)

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


def validate_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not VALID_ACTOR_ID_RE.fullmatch(actor_id):
        raise HostControlError("INVALID_REQUEST", "Invalid actor id.", returncode=2)
    return actor_id


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
        _require_nullable_str(row, "instances row", "thread_id")
        _require_nullable_int(row, "instances row", "browser_port")
    return rows


def _first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _emit_roles(control: HostControl, *, json_output: bool) -> int:
    roles = control.roles()
    if json_output:
        _emit_json({"roles": roles})
        return 0
    for row in roles:
        print("\t".join(str(row.get(key, "")) for key in ("id", "label", "scope")))
    return 0


def _emit_instances(instances: list[dict[str, object]], *, json_output: bool) -> int:
    if json_output:
        _emit_json({"instances": instances})
        return 0
    if not instances:
        print("No BuddySwitch instances found.")
        print("Start one with: ./buddyswitch-codex instance start --role <role>")
        return 0
    print("actor_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir")
    for row in instances:
        print(
            "\t".join(
                str(value if value is not None else "")
                for value in (
                    row.get("actor_id", ""),
                    row.get("role", ""),
                    row.get("status", ""),
                    row.get("app_server_health", ""),
                    row.get("thread_id", ""),
                    row.get("browser_port", ""),
                    row.get("updated_at", ""),
                    row.get("workspace_dir", ""),
                )
            )
        )
    return 0


def _emit_status(payload: dict[str, object], *, json_output: bool) -> int:
    if json_output:
        _emit_json(payload)
        return 0
    app_server = payload.get("app_server") if isinstance(payload.get("app_server"), dict) else {}
    daemon = payload.get("daemon") if isinstance(payload.get("daemon"), dict) else {}
    thread = payload.get("thread") if isinstance(payload.get("thread"), dict) else {}
    daemon_handlers = daemon.get("handlers") if isinstance(daemon.get("handlers"), dict) else {}
    registered = daemon_handlers.get("registered") if isinstance(daemon_handlers.get("registered"), list) else []
    print(f"Instance: {payload.get('actor_id')}")
    print(f"Buddy: {payload.get('role')}")
    print(f"Status: {payload.get('status')}")
    print(f"App-server health: {'healthy' if app_server.get('healthy') else 'unhealthy'}")
    print(f"Daemon health: {'healthy' if daemon.get('live') else 'unhealthy'}")
    print(f"Daemon handlers: {', '.join(str(item) for item in registered if isinstance(item, str))}")
    print("Delivery scope: daemon handler status is trigger-dispatch only; external channel delivery is separate.")
    print(f"Thread id: {payload.get('thread_id') or ''}")
    print(f"Thread status: {thread.get('status') or ''}")
    print(f"Browser port: {payload.get('browser_port') or ''}")
    print(f"Workspace: {payload.get('workspace_dir') or ''}")
    print(f"Updated: {payload.get('updated_at') or ''}")
    return 0


def _emit_capabilities(payload: dict[str, object], *, json_output: bool) -> int:
    if json_output:
        _emit_json(payload)
        return 0
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}

    def value(section_name: str, field_name: str) -> str:
        section = capabilities.get(section_name) if isinstance(capabilities.get(section_name), dict) else {}
        candidate = section.get(field_name)
        return candidate if isinstance(candidate, str) and candidate else "(missing)"

    print(f"actor_id: {payload.get('actor_id', '')}")
    print(f"parent level: {value('parent', 'level')}")
    print(f"parent model: {value('parent', 'model')}")
    print(f"parent effort: {value('parent', 'effort')}")
    print(f"side level: {value('side', 'level')}")
    print(f"side model: {value('side', 'model')}")
    print(f"side effort: {value('side', 'effort')}")
    return 0


def _command_roles(args: argparse.Namespace) -> int:
    return _emit_roles(HostControl(repo_root=args.repo_root), json_output=args.json)


def _command_start(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).start(args.role)
    if args.json:
        _emit_json(payload)
        return 0
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, list):
        for item in diagnostics:
            if isinstance(item, str) and item:
                print(item, file=sys.stderr)
    print(f"BuddySwitch instance: {payload.get('actor_id', '')} ({payload.get('role', '')})")
    print(f"Workspace: {payload.get('workspace_dir', '')}")
    print(f"Project workspace: {payload.get('project_workspace_dir', '')}")
    print(f"Instance record: {payload.get('instance_record', '')}")
    print(f"Input: ./buddyswitch-codex instance input {payload.get('actor_id', '')} --text \"<text>\"")
    print(f"Attach: ./buddyswitch-codex instance attach {payload.get('actor_id', '')}")
    print(f"Stop: ./buddyswitch-codex instance stop {payload.get('actor_id', '')}")
    print(f"Delete instance: ./buddyswitch-codex instance delete {payload.get('actor_id', '')} --yes")
    return 0


def _command_list(args: argparse.Namespace) -> int:
    return _emit_instances(
        HostControl(repo_root=args.repo_root).list_instances(args.role),
        json_output=args.json,
    )


def _command_status(args: argparse.Namespace) -> int:
    return _emit_status(HostControl(repo_root=args.repo_root).status(args.actor_id), json_output=args.json)


def _command_clear(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).clear(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Thread cleared: {payload.get('previous_thread_id', '')} -> {payload.get('thread_id', '')}")
    return 0


def _command_resume(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).resume(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Instance resumed: {payload.get('actor_id', '')}")
        print(f"Thread: {payload.get('thread_id', '')}")
    return 0


def _command_stop(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).stop(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Instance stopped: {payload.get('actor_id', '')}")
    return 0


def _command_delete(args: argparse.Namespace) -> int:
    if not args.yes:
        validate_actor_id(args.actor_id)
        print("BuddySwitch instance delete preview")
        print(f"Instance: {args.actor_id}")
        print(f"Instance root: {_shared_root_from_env() / 'instances' / args.actor_id}")
        print(f"Shared state kept: {_shared_root_from_env() / 'state'}")
        print("Run with --yes to delete this instance root.")
        return 0
    payload = HostControl(repo_root=args.repo_root).delete(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Instance deleted: {payload.get('actor_id', '')}")
    return 0


def _command_interrupt(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).interrupt(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Interrupted turn: {payload.get('turn_id') or ''}")
    return 0


def _command_compact(args: argparse.Namespace) -> int:
    payload = HostControl(repo_root=args.repo_root).compact(args.actor_id)
    if args.json:
        _emit_json(payload)
    else:
        print(f"Compaction started: {payload.get('thread_id') or ''}")
    return 0


def _command_capabilities(args: argparse.Namespace) -> int:
    control = HostControl(repo_root=args.repo_root)
    if args.capability_action == "get":
        return _emit_capabilities(control.capabilities_get(args.actor_id), json_output=args.json)
    return _emit_capabilities(
        control.capabilities_set(args.actor_id, args.parent, args.side),
        json_output=args.json,
    )


def _shared_root_from_env() -> Path:
    return HostControl()._shared_root()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(repo_root=REPO_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    roles = subparsers.add_parser("roles")
    roles.add_argument("--json", action="store_true")
    roles.set_defaults(func=_command_roles)

    start = subparsers.add_parser("start", usage="buddyswitch-codex instance start --role <role> [--json]")
    start.add_argument("--role", required=True)
    start.add_argument("--json", action="store_true")
    start.set_defaults(func=_command_start)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--role")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=_command_list)

    for name, func in (
        ("status", _command_status),
        ("clear", _command_clear),
        ("resume", _command_resume),
        ("stop", _command_stop),
        ("interrupt", _command_interrupt),
        ("compact", _command_compact),
    ):
        command = subparsers.add_parser(name)
        command.add_argument("actor_id")
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=func)

    delete = subparsers.add_parser("delete")
    delete.add_argument("actor_id")
    delete.add_argument("--yes", action="store_true")
    delete.add_argument("--json", action="store_true")
    delete.set_defaults(func=_command_delete)

    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("actor_id")
    capability_subparsers = capabilities.add_subparsers(dest="capability_action", required=True)
    cap_get = capability_subparsers.add_parser("get")
    cap_get.add_argument("--json", action="store_true")
    cap_get.set_defaults(func=_command_capabilities)
    cap_set = capability_subparsers.add_parser("set")
    cap_set.add_argument("--parent", required=True)
    cap_set.add_argument("--side", required=True)
    cap_set.add_argument("--json", action="store_true")
    cap_set.set_defaults(func=_command_capabilities)

    return parser


def _prevalidate_legacy_messages(argv: Sequence[str]) -> int | None:
    if not argv:
        return None
    command = argv[0]
    if command == "start":
        if "--" in argv:
            print(
                "instance start no longer accepts Codex args; use instance input after the service starts.",
                file=sys.stderr,
            )
            return 2
        for index, item in enumerate(argv):
            if item == "--role" and (index + 1 >= len(argv) or argv[index + 1].startswith("--")):
                print("Missing value for --role", file=sys.stderr)
                return 2
            if item == "--role=":
                print("Missing value for --role", file=sys.stderr)
                return 2
    if command == "capabilities" and len(argv) >= 3 and argv[2] == "get":
        for item in argv[3:]:
            if item != "--json":
                print(f"Unknown instance capabilities get option: {item}", file=sys.stderr)
                return 2
    return None


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    prevalidated = _prevalidate_legacy_messages(argv)
    if prevalidated is not None:
        return prevalidated
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except HostControlError as exc:
        print(exc.message, file=sys.stderr)
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
