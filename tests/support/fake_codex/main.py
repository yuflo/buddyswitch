"""Fake Codex CLI and app-server orchestration."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

from .state import append_calls
from .websocket import handle_websocket_connection

RUNNING = True


def _shared_root_is_temporary() -> bool:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    raw_run_root = os.environ.get("BUDDYSWITCH_TEST_RUN_ROOT")
    if not raw_shared_root or not raw_run_root:
        return False
    shared_root = Path(raw_shared_root).expanduser().resolve(strict=False)
    run_root = Path(raw_run_root).expanduser().resolve(strict=False)
    temporary_roots = (
        Path("/tmp").resolve(strict=False),
        Path("/var/tmp").resolve(strict=False),
        Path("/private/var/folders").resolve(strict=False),
        Path("/var/folders").resolve(strict=False),
    )
    return any(
        run_root.is_relative_to(temporary_root) and shared_root.is_relative_to(run_root)
        for temporary_root in temporary_roots
    )


def _handle_exit(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


for _sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(_sig, _handle_exit)
signal.signal(signal.SIGHUP, signal.SIG_IGN)


def remove_mcp_section(config_text: str, server_name: str) -> str:
    lines = config_text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    target = f"[mcp_servers.{server_name}]"
    while index < len(lines):
        if lines[index].strip() == target:
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("["):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    return "".join(output)


def upsert_mcp_section(codex_home: Path, server_name: str, argv: list[str]) -> None:
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config_text = remove_mcp_section(config_text, server_name).rstrip() + "\n\n"
    separator_index = argv.index("--")
    command = argv[separator_index + 1]
    args = argv[separator_index + 2 :]
    section = (
        f"[mcp_servers.{server_name}]\n"
        f"command = {json.dumps(command)}\n"
        f"args = {json.dumps(args)}\n"
    )
    config_path.write_text(config_text + section, encoding="utf-8")


def maybe_capture_prepare_probe() -> dict[str, object] | None:
    if not os.environ.get("BUDDYSWITCH_TEST_PREPARE_TEXT"):
        return None
    prepare_result = subprocess.run(
        [
            os.environ["BUDDYSWITCH_PYTHON"],
            "-m",
            "buddyswitch.application.entrypoints.diagnostics",
            "status",
        ],
        cwd=os.getcwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    payload: dict[str, object] = {
        "returncode": prepare_result.returncode,
        "stdout": prepare_result.stdout,
        "stderr": prepare_result.stderr,
        "json": None,
    }
    if prepare_result.stdout.strip():
        try:
            payload["json"] = json.loads(prepare_result.stdout)
        except json.JSONDecodeError as exc:
            payload["json_error"] = str(exc)
    return payload


def maybe_capture_broker_probe(entry: dict[str, object]) -> dict[str, object] | None:
    if not os.environ.get("BUDDYSWITCH_TEST_BROKER_STATUS"):
        return None
    instance_json = entry.get("instance_json")
    if not isinstance(instance_json, str) or not instance_json:
        return None
    instance_json_path = Path(instance_json)
    runtime_dir = instance_json_path.parent / "runtime"
    status_command = [
        os.environ["BUDDYSWITCH_PYTHON"],
        "-m",
        "buddyswitch.application.entrypoints.runtime_broker",
        "status",
        "--socket",
        entry.get("runtime_broker_socket") or str(runtime_dir / "runtime-broker.sock"),
        "--pid-file",
        str(runtime_dir / "runtime-broker.pid"),
        "--marker-file",
        str(runtime_dir / "runtime-broker.socket"),
        "--log-file",
        str(runtime_dir / "runtime-broker.log"),
        "--instance-json",
        str(instance_json_path),
    ]
    status_result = subprocess.run(
        status_command,
        cwd=os.getcwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    payload: dict[str, object] = {
        "returncode": status_result.returncode,
        "command": status_command,
        "stdout": status_result.stdout,
        "stderr": status_result.stderr,
        "json": None,
        "pid_file_text": (runtime_dir / "runtime-broker.pid").read_text(encoding="utf-8").strip()
        if (runtime_dir / "runtime-broker.pid").exists()
        else None,
        "marker_file_text": (runtime_dir / "runtime-broker.socket").read_text(encoding="utf-8").strip()
        if (runtime_dir / "runtime-broker.socket").exists()
        else None,
        "socket_exists": Path(str(entry.get("runtime_broker_socket"))).exists()
        if entry.get("runtime_broker_socket")
        else False,
    }
    if status_result.stdout.strip():
        try:
            payload["json"] = json.loads(status_result.stdout)
        except json.JSONDecodeError as exc:
            payload["json_error"] = str(exc)
    return payload


def maybe_capture_runtime_smoke() -> list[dict[str, object]] | None:
    if os.environ.get("BUDDYSWITCH_TEST_RUNTIME_COMMAND_SMOKE") != "1":
        return None
    rows: list[dict[str, object]] = []
    smoke_commands = (
        (
            "diagnostics.status",
            [
                os.environ["BUDDYSWITCH_PYTHON"],
                "-m",
                "buddyswitch.application.entrypoints.diagnostics",
                "status",
            ],
        ),
        (
            "context.summarize",
            [
                os.environ["BUDDYSWITCH_PYTHON"],
                "-m",
                "buddyswitch.application.entrypoints.env_client",
                "context",
                "summarize",
            ],
        ),
        (
            "actor_private.desc",
            [
                os.environ["BUDDYSWITCH_PYTHON"],
                "-m",
                "buddyswitch.application.entrypoints.env_client",
                "actor_private",
                "desc",
            ],
        ),
        (
            "search.status",
            [
                os.environ["BUDDYSWITCH_PYTHON"],
                "-m",
                "buddyswitch.application.entrypoints.env_client",
                "search",
                "status",
            ],
        ),
    )
    for name, command in smoke_commands:
        result = subprocess.run(
            command,
            cwd=os.getcwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        row: dict[str, object] = {
            "name": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "json": None,
        }
        if result.stdout.strip():
            try:
                row["json"] = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                row["json_error"] = str(exc)
        rows.append(row)
    return rows


def build_capture_payload(entry: dict[str, object], codex_home: Path, argv: list[str]) -> dict[str, object]:
    project_workspace_dir = entry["project_workspace_dir"]
    product_probe = None
    product_write = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_WRITE")
    product_read = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_READ")
    if project_workspace_dir and product_write:
        product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
        try:
            product_path.parent.mkdir(parents=True, exist_ok=True)
            product_path.write_text(product_write + "\n", encoding="utf-8")
            product_probe = {
                "ok": True,
                "path": str(product_path),
                "content": product_path.read_text(encoding="utf-8").strip(),
            }
        except Exception as exc:  # pragma: no cover - probe diagnostics only
            product_probe = {
                "ok": False,
                "path": str(product_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    elif project_workspace_dir and product_read:
        product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
        product_probe = {
            "path": str(product_path),
            "exists": product_path.exists(),
            "content": product_path.read_text(encoding="utf-8").strip() if product_path.exists() else None,
        }

    projects_app_path = Path("projects/app")
    projects_app_probe: dict[str, object] = {
        "path": str(projects_app_path),
        "exists": projects_app_path.exists(),
        "resolved": None,
    }
    try:
        projects_app_probe["resolved"] = str(projects_app_path.resolve(strict=True))
    except FileNotFoundError:
        pass
    except OSError as exc:
        projects_app_probe["resolve_error"] = str(exc)

    relative_probe = None
    relative_write_path = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH")
    relative_write_content = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT")
    relative_read_path = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_READ_PATH")
    if relative_write_path or relative_read_path:
        relative_probe = {}
    if relative_write_path:
        write_target = projects_app_path / relative_write_path
        write_value = relative_write_content if relative_write_content is not None else "relative-write"
        try:
            write_target.parent.mkdir(parents=True, exist_ok=True)
            write_target.write_text(write_value + "\n", encoding="utf-8")
            relative_probe["write"] = {
                "ok": True,
                "path": str(write_target),
                "resolved": str(write_target.resolve(strict=True)),
                "exists": write_target.exists(),
                "content": write_target.read_text(encoding="utf-8").strip(),
            }
        except Exception as exc:  # pragma: no cover - probe diagnostics only
            relative_probe["write"] = {
                "ok": False,
                "path": str(write_target),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "exists": write_target.exists(),
            }
    if relative_read_path:
        read_target = projects_app_path / relative_read_path
        relative_probe["read"] = {
            "path": str(read_target),
            "resolved": str(read_target.resolve(strict=False)),
            "exists": read_target.exists(),
            "content": read_target.read_text(encoding="utf-8").strip() if read_target.exists() else None,
        }

    instance_payload = None
    if entry["instance_json"]:
        instance_payload = json.loads(Path(str(entry["instance_json"])).read_text(encoding="utf-8"))

    counter_path = codex_home / "launch-count.txt"
    launch_count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
    launch_count += 1
    counter_path.write_text(f"{launch_count}\n", encoding="utf-8")

    auth_payload = None
    auth_path = codex_home / "auth.json"
    if auth_path.exists():
        auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))

    return {
        **entry,
        "product_probe": product_probe,
        "projects_app_probe": projects_app_probe,
        "relative_probe": relative_probe,
        "prepare_probe": maybe_capture_prepare_probe(),
        "broker_status_probe": maybe_capture_broker_probe(entry),
        "runtime_command_smoke": maybe_capture_runtime_smoke(),
        "launch_count": launch_count,
        "config_toml": (codex_home / "config.toml").read_text(encoding="utf-8")
        if (codex_home / "config.toml").exists()
        else "",
        "auth_json": auth_payload,
        "instance_json_payload": instance_payload,
    }


def write_capture(payload: dict[str, object]) -> None:
    capture_path = os.environ.get("BUDDYSWITCH_TEST_CAPTURE")
    if not capture_path:
        return
    Path(capture_path).write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def run_fake_app_server(socket_url: str, entry: dict[str, object]) -> int:
    socket_path = socket_url.removeprefix("unix://")
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    if os.environ.get("BUDDYSWITCH_TEST_APP_SERVER_EXIT_AFTER_START") == "1":
        return 1

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    threads: list[threading.Thread] = []

    def serve_client(client: socket.socket) -> None:
        try:
            handle_websocket_connection(client, entry, is_running=lambda: RUNNING)
        finally:
            client.close()

    try:
        server.bind(str(path))
        server.listen(5)
        server.settimeout(0.2)
        while RUNNING:
            try:
                client, _addr = server.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                break
            thread = threading.Thread(target=serve_client, args=(client,), daemon=True)
            thread.start()
            threads.append(thread)
        return 0
    finally:
        server.close()
        for thread in threads:
            thread.join(timeout=0.2)
        path.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    invoked_cwd = os.environ.pop("BUDDYSWITCH_TEST_INVOKED_CWD", None)
    if invoked_cwd:
        os.chdir(invoked_cwd)
    if argv == ["--version"]:
        print("codex-cli fake-test")
        return 0
    if not _shared_root_is_temporary():
        print(
            "fake Codex requires a temporary BUDDYSWITCH_SHARED_ROOT "
            f"(shared={os.environ.get('BUDDYSWITCH_SHARED_ROOT')!r}, "
            f"run={os.environ.get('BUDDYSWITCH_TEST_RUN_ROOT')!r})",
            file=sys.stderr,
        )
        return 2
    codex_home = Path(os.environ["CODEX_HOME"])
    entry: dict[str, object] = {
        "argv": argv,
        "cwd": os.getcwd(),
        "home": os.environ.get("HOME"),
        "codex_home": os.environ.get("CODEX_HOME"),
        "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
        "tmpdir": os.environ.get("TMPDIR"),
        "tmp": os.environ.get("TMP"),
        "temp": os.environ.get("TEMP"),
        "tmpprefix": os.environ.get("TMPPREFIX"),
        "active_role": os.environ.get("BUDDYSWITCH_ROLE_ID"),
        "actor_id": os.environ.get("BUDDYSWITCH_ACTOR_ID"),
        "instance_json": os.environ.get("BUDDYSWITCH_INSTANCE_JSON"),
        "project_source": os.environ.get("BUDDYSWITCH_PROJECT_SOURCE"),
        "actor_private_dir": os.environ.get("BUDDYSWITCH_ACTOR_PRIVATE_DIR"),
        "instance_tmp": os.environ.get("BUDDYSWITCH_INSTANCE_TMP"),
        "project_workspace_dir": os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR"),
        "runtime_broker_socket": os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_SOCKET"),
    }
    append_calls(entry)

    if argv[:2] == ["mcp", "remove"] and len(argv) >= 3:
        config_path = codex_home / "config.toml"
        config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        config_path.write_text(remove_mcp_section(config_text, argv[2]), encoding="utf-8")
        return 0

    if argv[:2] == ["mcp", "add"] and len(argv) >= 3:
        if os.environ.get("BUDDYSWITCH_TEST_FAIL_MCP_ADD_NAME") == argv[2]:
            print(f"simulated mcp add failure: {argv[2]}", file=sys.stderr)
            return 42
        upsert_mcp_section(codex_home, argv[2], argv)
        return 0

    write_capture(build_capture_payload(entry, codex_home, argv))

    if argv[:2] == ["app-server", "--listen"] and len(argv) >= 3:
        return run_fake_app_server(argv[2], entry)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
