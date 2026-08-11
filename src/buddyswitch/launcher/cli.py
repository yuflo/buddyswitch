"""Public BuddySwitch CLI adapter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


HELPER_DIR = Path(__file__).resolve().parent
SHELL_ROOT = HELPER_DIR / "shell"
PACKAGE_ROOT = HELPER_DIR.parent
APP_SERVER_SHELL = PACKAGE_ROOT / "foundation" / "app_server" / "shell" / "app_server.sh"


def _shared_root_from_env() -> Path:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        return Path(raw_shared_root.strip()).expanduser()
    source_home = os.environ.get("BUDDYSWITCH_SOURCE_HOME") or os.environ.get("HOME")
    if isinstance(source_home, str) and source_home.strip():
        return Path(source_home.strip()).expanduser() / ".codex-buddyswitch"
    return Path.home() / ".codex-buddyswitch"


def _validate_reset_root(shared_root: Path) -> None:
    root = shared_root.expanduser()
    if str(root) in {"", "/"}:
        raise cli_contract.CliError("INVALID_ARGUMENT", f"Reset blocked: unsafe shared root '{root}'.")
    if root.name != ".codex-buddyswitch":
        raise cli_contract.CliError(
            "INVALID_ARGUMENT",
            "Reset blocked: BUDDYSWITCH_SHARED_ROOT must target a '.codex-buddyswitch' directory.",
        )
    if root.is_symlink():
        raise cli_contract.CliError(
            "INVALID_ARGUMENT",
            f"Reset blocked: shared root is a symlink ({root}).",
        )
    if root.exists() and not root.is_dir():
        raise cli_contract.CliError(
            "INVALID_ARGUMENT",
            f"Reset blocked: shared root is not a directory ({root}).",
        )


_SHARED_ROOT = _shared_root_from_env()
os.environ.setdefault("BUDDYSWITCH_SHARED_ROOT", str(_SHARED_ROOT))
os.environ.setdefault("BUDDYSWITCH_STATE_ROOT", str(_SHARED_ROOT / "state"))

from buddyswitch.foundation.actor_runtime import codex_runtime  # noqa: E402
from buddyswitch.foundation.actor_runtime import session as actor_session  # noqa: E402
from buddyswitch.launcher import (  # noqa: E402
    cli_contract,
    host_control,
    runtime_lock,
)
from buddyswitch.foundation.daemon import central_process, central_service  # noqa: E402


DASH = "--"
YES_FLAG = DASH + "yes"


class HelpRequested(Exception):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


class WebProcessExited(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class CommandResult:
    kind: str
    data: object


_HELP_TEMPLATE = """Usage:
  buddyswitch-codex instance roles
  buddyswitch-codex instance start --role <role>
  buddyswitch-codex instance list [--role <role>]
  buddyswitch-codex instance status <actor-id>
  buddyswitch-codex instance input <actor-id> --text <text>
  buddyswitch-codex instance interrupt <actor-id>
  buddyswitch-codex instance compact <actor-id>
  buddyswitch-codex instance clear <actor-id>
  buddyswitch-codex instance attach <actor-id>
  buddyswitch-codex instance resume <actor-id>
  buddyswitch-codex instance stop <actor-id>
  buddyswitch-codex instance delete <actor-id> --yes
  buddyswitch-codex instance capabilities <actor-id> get
  buddyswitch-codex instance capabilities <actor-id> set --parent <level> --side <level>

{contributed_usage}

  buddyswitch-codex data cleanup (--role <role>|--all-data) --yes
  buddyswitch-codex env status
  buddyswitch-codex env browser status [--instance <actor-id>] [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex env browser ensure --instance <actor-id> [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex env browser release --instance <actor-id>
  buddyswitch-codex env reset --yes
  buddyswitch-codex web [--host 127.0.0.1] [--port 8765]
  buddyswitch-codex help

Commands:
  instance  Manage BuddySwitch product-mode instances.
{contributed_commands}
  data      Manage BuddySwitch data cleanup commands.
  env       Manage BuddySwitch environment status and reset commands.
  web       Run the local BuddySwitch web management server.
  help      Show this help message.
"""


def _command_registrations(
    registrations: tuple[cli_contract.CliCommandRegistration, ...],
) -> dict[str, cli_contract.CliCommandRegistration]:
    if not isinstance(registrations, tuple):
        raise ValueError("CLI registrations must be a tuple")
    reserved = {"instance", "data", "env", "web", "help"}
    configured: dict[str, cli_contract.CliCommandRegistration] = {}
    for registration in registrations:
        if not isinstance(registration, cli_contract.CliCommandRegistration):
            raise ValueError("CLI contribution must be CliCommandRegistration")
        if (
            not isinstance(registration.name, str)
            or not registration.name.strip()
        ):
            raise ValueError("CLI command name must be a non-empty string")
        name = registration.name.strip()
        if name in reserved or name in configured:
            raise ValueError(f"duplicate CLI command: {name}")
        if not callable(registration.handler):
            raise ValueError(f"CLI command handler for '{name}' must be callable")
        configured[name] = registration
    return configured


def render_help(
    registrations: tuple[cli_contract.CliCommandRegistration, ...],
) -> str:
    configured = _command_registrations(registrations)
    rows = [
        row
        for registration in configured.values()
        for row in registration.help_rows
    ]
    usage = [row for row in rows if row.startswith("  buddyswitch-codex ")]
    commands = [row for row in rows if not row.startswith("  buddyswitch-codex ")]
    return _HELP_TEMPLATE.format(
        contributed_usage="\n".join(usage),
        contributed_commands="\n".join(commands),
    )


HELP_TEXT = render_help(())


def main(
    argv: Sequence[str] | None = None,
    *,
    command_registrations: tuple[
        cli_contract.CliCommandRegistration, ...
    ] = (),
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        commands = _command_registrations(command_registrations)
        help_text = render_help(command_registrations)
        if _is_help(args):
            raise HelpRequested(help_text)
        result = _dispatch(args, commands=commands, help_text=help_text)
    except HelpRequested as exc:
        sys.stdout.write(exc.text)
        return 0
    except WebProcessExited as exc:
        return exc.status
    except Exception as exc:
        error = _map_exception(exc)
        cli_contract.emit(cli_contract.failure(error), sys.stdout)
        return cli_contract.exit_code(error)

    cli_contract.emit(cli_contract.success(result.kind, result.data), sys.stdout)
    return 0


def _is_help(args: list[str]) -> bool:
    return args in (["help"], [DASH + "help"], ["-h"]) or DASH + "help" in args or "-h" in args


def _dispatch(
    args: list[str],
    *,
    commands: dict[str, cli_contract.CliCommandRegistration],
    help_text: str,
) -> CommandResult | cli_contract.CliCommandResult:
    if not args:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "BuddySwitch command is required")
    command, rest = args[0], args[1:]
    if command == "instance":
        return _dispatch_instance(rest, help_text=help_text)
    if command in commands:
        return commands[command].handler(rest)
    if command == "data":
        return _dispatch_data(rest)
    if command == "env":
        return _dispatch_env(rest)
    if command == "web":
        raise WebProcessExited(_run_web(rest))
    raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown top-level command: {command}")


def _dispatch_instance(args: list[str], *, help_text: str) -> CommandResult:
    if not args:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "instance command is required")
    command, rest = args[0], args[1:]
    control = host_control.HostControl()
    if command == "roles":
        _require_no_args(rest, "instance roles")
        return CommandResult("instance.roles", {"roles": control.roles()})
    if command == "help":
        _require_no_args(rest, "instance help")
        raise HelpRequested(help_text)
    if command == "start":
        role = _single_required_option(rest, DASH + "role", "instance start")
        return CommandResult("instance.start", control.start(role))
    if command == "list":
        role = _optional_single_option(rest, DASH + "role", "instance list")
        return CommandResult("instance.list", {"instances": control.list_instances(role)})
    if command == "status":
        actor_id = _single_positional(rest, "actor id", "instance status")
        return CommandResult("instance.status", control.status(actor_id))
    if command == "input":
        actor_id, text = _parse_input(rest)
        session = _actor_session()
        return CommandResult("instance.input", session.input(actor_id, text))
    if command == "attach":
        actor_id = _single_positional(rest, "actor id", "instance attach")
        _actor_session().exec_attach(actor_id)
    if command == "interrupt":
        actor_id = _single_positional(rest, "actor id", "instance interrupt")
        return CommandResult("instance.interrupt", control.interrupt(actor_id))
    if command == "compact":
        actor_id = _single_positional(rest, "actor id", "instance compact")
        return CommandResult("instance.compact", control.compact(actor_id))
    if command == "clear":
        actor_id = _single_positional(rest, "actor id", "instance clear")
        return CommandResult("instance.clear", control.clear(actor_id))
    if command == "resume":
        actor_id = _single_positional(rest, "actor id", "instance resume")
        return CommandResult("instance.resume", control.resume(actor_id))
    if command == "stop":
        actor_id = _single_positional(rest, "actor id", "instance stop")
        return CommandResult("instance.stop", control.stop(actor_id))
    if command == "delete":
        actor_id = _destructive_actor(rest, "instance delete")
        return CommandResult("instance.delete", control.delete(actor_id))
    if command == "capabilities":
        return _dispatch_capabilities(rest, control)
    raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown instance command: {command}")


def _dispatch_capabilities(args: list[str], control: host_control.HostControl) -> CommandResult:
    if len(args) < 2:
        raise cli_contract.CliError("INVALID_ARGUMENT", "instance capabilities requires <actor-id> get|set")
    actor_id, action, rest = args[0], args[1], args[2:]
    if action == "get":
        _require_no_args(rest, "instance capabilities get")
        return CommandResult("instance.capabilities.get", control.capabilities_get(actor_id))
    if action == "set":
        values = _parse_required_options(
            rest,
            required=(DASH + "parent", DASH + "side"),
            context="instance capabilities set",
        )
        return CommandResult(
            "instance.capabilities.set",
            control.capabilities_set(actor_id, values[DASH + "parent"], values[DASH + "side"]),
        )
    raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown instance capabilities command: {action}")


def _dispatch_data(args: list[str]) -> CommandResult:
    if not args:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "data command is required")
    command, rest = args[0], args[1:]
    if command != "cleanup":
        raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown data command: {command}")
    cleanup_args = _parse_cleanup_args(rest)
    completed = _run_locked_shell_owner(_cleanup_locked_script(), cleanup_args)
    data = _owner_json_data(completed)
    return CommandResult("data.cleanup", data)


def _dispatch_env(args: list[str]) -> CommandResult:
    if not args:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "env command is required")
    command, rest = args[0], args[1:]
    if command == "status":
        _require_no_args(rest, "env status")
        shared_root = _shared_root_from_env()
        instance_count = 0
        instances_root = shared_root / "instances"
        if instances_root.is_dir():
            instance_count = sum(1 for row in instances_root.iterdir() if row.is_dir())
        browser_state = "active" if _browser_is_active() else "inactive"
        return CommandResult(
            "env.status",
            {
                "shared_root": str(shared_root),
                "instance_count": instance_count,
                "browser_state": browser_state,
            },
        )
    if command == "reset":
        _require_yes_only(rest, "env reset")
        shared_root = _shared_root_from_env()
        _validate_reset_root(shared_root)
        existed = shared_root.is_dir()
        if not existed:
            return CommandResult("env.reset", {"shared_root": str(shared_root), "removed": False})
        _run_locked_shell_owner(_reset_locked_script(), [])
        return CommandResult("env.reset", {"shared_root": str(shared_root), "removed": existed and not shared_root.exists()})
    if command == "browser":
        return _dispatch_env_browser(rest)
    raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown env command: {command}")


def _dispatch_env_browser(args: list[str]) -> CommandResult:
    if not args:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "env browser command is required")
    command, rest = args[0], args[1:]
    if command not in {"status", "ensure", "release"}:
        raise cli_contract.CliError("UNKNOWN_COMMAND", f"Unknown env browser command: {command}")
    parsed = _parse_browser_args(rest, command)
    actor_id = parsed.pop("instance", None)
    shell_args = [command]
    for key, value in parsed.items():
        shell_args.extend([DASH + key.replace("_", "-"), value])
    if command == "ensure" and "port" not in parsed:
        _validate_env_browser_port()
    if command in {"ensure", "release"}:
        if actor_id is None:
            raise cli_contract.CliError("INVALID_ARGUMENT", f"env browser {command} requires --instance <actor-id>")
        _validate_actor_id(actor_id)
        _require_known_actor(actor_id)
        completed = _run_locked_shell_owner(_browser_locked_script(actor_id), shell_args)
    else:
        if actor_id is not None:
            _require_known_actor(actor_id)
        completed = _run_shell_owner(_browser_script(actor_id), shell_args)
    return CommandResult(f"env.browser.{command}", _owner_json_data(completed))


def _run_web(args: list[str]) -> int:
    parsed = _parse_web_args(args)
    paths = central_service.central_daemon_paths(_shared_root_from_env())
    daemon_result = central_process.start_central_daemon(paths)
    env = os.environ.copy()
    env["BUDDYSWITCH_CENTRAL_DAEMON_SOCKET"] = str(daemon_result.get("socket_path") or paths.socket_path)
    argv = [str(_python()), "-m", "buddyswitch.application.entrypoints.web"]
    if parsed.get("host") is not None:
        argv.extend([DASH + "host", str(parsed["host"])])
    if parsed.get("port") is not None:
        argv.extend([DASH + "port", str(parsed["port"])])
    try:
        completed = subprocess.run(argv, cwd=PACKAGE_ROOT, env=env, check=False)
        return int(completed.returncode)
    finally:
        central_process.stop_if_idle(paths)


def _actor_session() -> actor_session.ActorSession:
    return actor_session.ActorSession(
        shared_root=_shared_root_from_env(),
    )


def _single_positional(args: list[str], label: str, context: str) -> str:
    if len(args) != 1 or args[0].startswith("-"):
        raise cli_contract.CliError("INVALID_ARGUMENT", f"{context} requires <{label}>")
    return args[0]


def _require_no_args(args: list[str], context: str) -> None:
    if args:
        raise cli_contract.CliError("INVALID_ARGUMENT", f"{context} does not accept: {' '.join(args)}")


def _single_required_option(args: list[str], option: str, context: str) -> str:
    return cli_contract.single_required_option(args, option, context)


def _optional_single_option(args: list[str], option: str, context: str) -> str | None:
    return cli_contract.optional_single_option(args, option, context)


def _parse_required_options(args: list[str], *, required: tuple[str, ...], context: str) -> dict[str, str]:
    return cli_contract.parse_required_options(
        args,
        required=required,
        context=context,
    )


def _parse_options(args: list[str], *, allowed: tuple[str, ...], context: str) -> dict[str, str]:
    return cli_contract.parse_options(
        args,
        allowed=allowed,
        context=context,
    )


def _parse_input(args: list[str]) -> tuple[str, str]:
    if not args or args[0].startswith("-"):
        raise cli_contract.CliError("INVALID_ARGUMENT", "instance input requires <actor-id>")
    actor_id = args[0]
    rest = args[1:]
    if not rest or rest[0] != DASH + "text":
        raise cli_contract.CliError("INVALID_ARGUMENT", "instance input requires --text <value>")
    if len(rest) < 2 or not rest[1]:
        raise cli_contract.CliError("INVALID_ARGUMENT", "instance input requires --text <value>")
    if len(rest) > 2:
        raise cli_contract.CliError("INVALID_ARGUMENT", f"instance input does not accept: {' '.join(rest[2:])}")
    text = rest[1]
    return actor_id, text


def _destructive_actor(args: list[str], context: str) -> str:
    if not args or args[0].startswith("-"):
        raise cli_contract.CliError("INVALID_ARGUMENT", f"{context} requires <actor-id>")
    actor_id, rest = args[0], args[1:]
    if rest != [YES_FLAG]:
        if YES_FLAG not in rest:
            raise cli_contract.CliError("CONFIRMATION_REQUIRED", f"{context} requires {YES_FLAG}")
        raise cli_contract.CliError("INVALID_ARGUMENT", f"{context} does not accept: {' '.join(rest)}")
    return actor_id


def _require_yes_only(args: list[str], context: str) -> None:
    if args != [YES_FLAG]:
        if YES_FLAG not in args:
            raise cli_contract.CliError("CONFIRMATION_REQUIRED", f"{context} requires {YES_FLAG}")
        raise cli_contract.CliError("INVALID_ARGUMENT", f"{context} does not accept: {' '.join(args)}")


def _parse_cleanup_args(args: list[str]) -> list[str]:
    if YES_FLAG not in args:
        raise cli_contract.CliError("CONFIRMATION_REQUIRED", f"data cleanup requires {YES_FLAG}")
    target: list[str] | None = None
    cleaned: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == YES_FLAG:
            cleaned.append(arg)
            index += 1
        elif arg == DASH + "all-data":
            if target is not None:
                raise cli_contract.CliError("INVALID_ARGUMENT", "data cleanup target must be specified exactly once")
            target = [arg]
            cleaned.append(arg)
            index += 1
        elif arg == DASH + "role":
            if target is not None:
                raise cli_contract.CliError("INVALID_ARGUMENT", "data cleanup target must be specified exactly once")
            if index + 1 >= len(args) or args[index + 1].startswith("-"):
                raise cli_contract.CliError("INVALID_ARGUMENT", "data cleanup requires --role <role>")
            target = [arg, args[index + 1]]
            cleaned.extend(target)
            index += 2
        else:
            raise cli_contract.CliError("INVALID_ARGUMENT", f"data cleanup does not accept: {arg}")
    if target is None:
        raise cli_contract.CliError("INVALID_ARGUMENT", "data cleanup target is required")
    return cleaned


def _parse_browser_args(args: list[str], command: str) -> dict[str, str]:
    allowed = {DASH + "instance", DASH + "port", DASH + "profile-dir"}
    parsed: dict[str, str] = {}
    index = 0
    while index < len(args):
        option = args[index]
        if option not in allowed:
            raise cli_contract.CliError("INVALID_ARGUMENT", f"env browser {command} does not accept: {option}")
        if index + 1 >= len(args) or args[index + 1].startswith("-"):
            raise cli_contract.CliError("INVALID_ARGUMENT", f"env browser {command} requires {option} <value>")
        key = option.removeprefix(DASH).replace("-", "_")
        if key in parsed:
            raise cli_contract.CliError("INVALID_ARGUMENT", f"env browser {command} received {option} more than once")
        parsed[key] = args[index + 1]
        index += 2
    if command == "release":
        extras = sorted(set(parsed) - {"instance"})
        if extras:
            raise cli_contract.CliError("INVALID_ARGUMENT", "env browser release only accepts --instance")
    if "port" in parsed:
        _validate_port(parsed["port"], label="--port")
    return parsed


def _parse_web_args(args: list[str]) -> dict[str, str]:
    parsed = _parse_options(args, allowed=(DASH + "host", DASH + "port"), context="web")
    if DASH + "port" in parsed:
        _validate_port(parsed[DASH + "port"], label="--port")
    return {
        "host": parsed.get(DASH + "host"),
        "port": parsed.get(DASH + "port"),
    }


def _require_known_actor(actor_id: str) -> None:
    _validate_actor_id(actor_id)
    for row in host_control.HostControl().list_instances():
        if row.get("actor_id") == actor_id:
            return
    raise cli_contract.CliError("NOT_FOUND", f"actor instance not found: {actor_id}", {"actor_id": actor_id})


def _validate_actor_id(actor_id: str) -> None:
    try:
        host_control.validate_actor_id(actor_id)
    except host_control.HostControlError as exc:
        raise _map_host_control_error(exc) from exc


def _validate_port(value: str, *, label: str) -> None:
    try:
        port = int(value)
    except ValueError as exc:
        raise cli_contract.CliError("INVALID_ARGUMENT", f"Invalid value for {label}: {value}") from exc
    if port < 1 or port > 65535:
        raise cli_contract.CliError("INVALID_ARGUMENT", f"Invalid value for {label}: {value}")


def _validate_env_browser_port() -> None:
    raw = os.environ.get("BUDDYSWITCH_BROWSER_PORT")
    if raw is None or raw == "":
        return
    _validate_port(raw, label="BUDDYSWITCH_BROWSER_PORT")


def _python() -> Path:
    raw = os.environ.get("BUDDYSWITCH_PYTHON")
    if not isinstance(raw, str) or not raw.strip():
        raise cli_contract.CliError("RUNTIME_UNAVAILABLE", "BUDDYSWITCH_PYTHON is not initialized")
    return Path(raw.strip())


def _run_shell_owner(script: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["bash", "-c", script, "buddyswitch-owner", *args],
        cwd=SHELL_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise _owner_error(completed)
    return completed


def _run_locked_shell_owner(script: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    try:
        with runtime_lock.hold_runtime_lock(
            str(_shared_root_from_env()),
            runtime_lock.resolve_timeout(None),
        ):
            completed = subprocess.run(
                ["bash", "-c", script, "buddyswitch-locked-owner", *args],
                cwd=SHELL_ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
    except runtime_lock.RuntimeLockBusyError as exc:
        raise cli_contract.CliError("CONFLICT", str(exc)) from exc
    if completed.returncode != 0:
        raise _owner_error(completed)
    return completed


def _owner_error(completed: subprocess.CompletedProcess[str]) -> cli_contract.CliError:
    payload = _maybe_json_object(completed.stdout)
    payload_error = payload.get("error") if payload is not None else None
    payload_message = payload_error.get("message") if isinstance(payload_error, dict) else None
    message = (
        _first_nonempty_line(completed.stderr)
        or (payload_message if isinstance(payload_message, str) and payload_message.strip() else None)
        or _first_nonempty_line(completed.stdout)
        or "Command failed"
    )
    if completed.returncode == 2:
        return cli_contract.CliError("INVALID_ARGUMENT", message)
    if completed.returncode in {3, 4}:
        return cli_contract.CliError("CONFLICT", message)
    if completed.returncode == 5:
        return cli_contract.CliError("RUNTIME_UNAVAILABLE", message)
    if message.startswith("Reset blocked:"):
        return cli_contract.CliError("INVALID_ARGUMENT", message)
    return cli_contract.CliError("EXECUTION_FAILED", message)


def _browser_is_active() -> bool:
    completed = subprocess.run(
        [
            "bash",
            "-c",
        _source_helpers_script(
            """
buddyswitch_browser_init_defaults >/dev/null
if buddyswitch_browser_is_active; then
  exit 0
fi
exit 1
""",
            include_browser=True,
            include_app_server=True,
        ),
            "buddyswitch-browser-status",
        ],
        cwd=SHELL_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _maybe_json_object(text: str | None) -> dict[str, object] | None:
    if not text or not text.strip():
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _owner_json_data(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    text = completed.stdout.strip()
    if not text:
        raise cli_contract.CliError("EXECUTION_FAILED", "Owner command emitted no JSON output")
    payload = _maybe_json_object(text)
    if payload is None:
        raise cli_contract.CliError("EXECUTION_FAILED", "Owner command emitted invalid JSON output")
    return payload


def _first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def _source_helpers_script(
    body: str,
    *,
    include_browser: bool = False,
    include_app_server: bool = False,
    include_cleanup: bool = False,
) -> str:
    sources = [
        f'source "{SHELL_ROOT / "env.sh"}"',
    ]
    if include_browser:
        sources.append(f'source "{SHELL_ROOT / "browser_cockpit.sh"}"')
    if include_app_server:
        sources.append(f'source "{APP_SERVER_SHELL}"')
    if include_cleanup:
        sources.append(f'source "{SHELL_ROOT / "cleanup.sh"}"')
    return "\n".join(
        [
            "set -euo pipefail",
            *sources,
            "buddyswitch_env_init",
            body.strip(),
        ]
    )


def _reset_locked_script() -> str:
    return _source_helpers_script(
        """
buddyswitch_require_runtime_lock
buddyswitch_validate_reset_root
active_count="$(buddyswitch_count_active_app_servers)"
if [[ "${active_count}" -gt 0 ]]; then
  echo "Reset blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
  exit 3
fi
if buddyswitch_browser_is_active; then
  echo "Reset blocked: active browser cockpit detected." >&2
  exit 3
fi
if [[ -d "${BUDDYSWITCH_SHARED_ROOT}" ]]; then
  buddyswitch_remove_owned_path "${BUDDYSWITCH_SHARED_ROOT}"
fi
""",
        include_browser=True,
        include_app_server=True,
    )


def _cleanup_locked_script() -> str:
    return _source_helpers_script(
        """
buddyswitch_cleanup_run_locked "$@"
""",
        include_browser=True,
        include_app_server=True,
        include_cleanup=True,
    )


def _browser_script(actor_id: str | None) -> str:
    bind = ""
    if actor_id is not None:
        _validate_actor_id(actor_id)
        bind = f'''
buddyswitch_env_bind_instance "{actor_id}"
browser_port="$("${{BUDDYSWITCH_PYTHON}}" - "${{BUDDYSWITCH_INSTANCE_JSON}}" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload.get("browser_port")
if isinstance(value, int):
    print(value)
PY
)"
if [[ -n "${{browser_port}}" ]]; then
  export BUDDYSWITCH_BROWSER_PORT="${{browser_port}}"
fi
'''
    else:
        bind = """
export BUDDYSWITCH_BROWSER_PROFILE_DIR="${BUDDYSWITCH_RUN_STATE_DIR}/browser-status-profile"
export BUDDYSWITCH_BROWSER_PROFILE_DIR_EXPLICIT=1
export BUDDYSWITCH_BROWSER_LOG_FILE="${BUDDYSWITCH_RUN_STATE_DIR}/chrome-cockpit.log"
export BUDDYSWITCH_BROWSER_LOG_FILE_EXPLICIT=1
"""
    return _source_helpers_script(
        f"""
{bind}
buddyswitch_browser_main "$@"
""",
        include_browser=True,
    )


def _browser_locked_script(actor_id: str) -> str:
    return _source_helpers_script(
        f"""
buddyswitch_require_runtime_lock
buddyswitch_env_bind_instance "{actor_id}"
buddyswitch_browser_main "$@"
""",
        include_browser=True,
    )


def _map_exception(exc: BaseException) -> cli_contract.CliError:
    if isinstance(exc, cli_contract.CliError):
        return cli_contract.normalize_error(exc)
    if isinstance(exc, host_control.HostControlError):
        return _map_host_control_error(exc)
    if isinstance(exc, actor_session.ActorSessionError):
        return _map_actor_session_error(exc)
    if isinstance(exc, codex_runtime.CodexRuntimeError):
        public_code = "RUNTIME_UNAVAILABLE" if exc.code == "RUNTIME_UNAVAILABLE" else "RUNTIME_MISMATCH"
        return cli_contract.CliError(public_code, str(exc))
    return cli_contract.normalize_error(exc)


def _map_host_control_error(exc: host_control.HostControlError) -> cli_contract.CliError:
    if exc.timed_out or exc.code == "COMMAND_TIMEOUT":
        return cli_contract.CliError("TIMEOUT", exc.message)
    if exc.code == "INVALID_REQUEST":
        return cli_contract.CliError("INVALID_ARGUMENT", exc.message)
    if exc.code == "NOT_FOUND":
        return cli_contract.CliError("NOT_FOUND", exc.message)
    if exc.code == "CAPABILITY_CONFIG_INVALID":
        return cli_contract.CliError("PRECONDITION_FAILED", exc.message)
    if exc.code in {"LIFECYCLE_BLOCKED", "LOCK_BUSY"}:
        return cli_contract.CliError("CONFLICT", exc.message)
    if exc.code in {"COMMAND_FAILED", "CAPABILITY_CONFIG_WRITE_FAILED"}:
        return cli_contract.CliError("EXECUTION_FAILED", exc.message)
    if exc.code in {"RUNTIME_UNAVAILABLE", "RUNTIME_MISMATCH"}:
        return cli_contract.CliError(exc.code, exc.message)
    return cli_contract.CliError("INTERNAL_ERROR", "Unexpected internal error")


def _map_actor_session_error(exc: actor_session.ActorSessionError) -> cli_contract.CliError:
    message = str(exc)
    lowered = message.lower()
    if "not found" in lowered:
        return cli_contract.CliError("NOT_FOUND", message)
    if "invalid actor id" in lowered or "is required" in lowered:
        return cli_contract.CliError("INVALID_ARGUMENT", message)
    if "unhealthy" in lowered or "no thread id" in lowered:
        return cli_contract.CliError("RUNTIME_UNAVAILABLE", message)
    if "parent capability invalid" in lowered:
        return cli_contract.CliError("PRECONDITION_FAILED", message)
    if (
        "parent settings update failed" in lowered
        or "input turn failed" in lowered
        or "thread/resume failed" in lowered
        or "thread/resume returned unexpected thread id" in lowered
    ):
        return cli_contract.CliError("EXECUTION_FAILED", message)
    return cli_contract.CliError("INTERNAL_ERROR", "Unexpected internal error")
