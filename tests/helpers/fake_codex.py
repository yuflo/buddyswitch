#!/usr/bin/env python3
"""Fake codex executable for BuddySwitch launcher tests."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
RUNNING = True
MEMORY_STATE: dict[str, object] = {}


def _handle_exit(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


for _sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(_sig, _handle_exit)
signal.signal(signal.SIGHUP, signal.SIG_IGN)


def append_calls(payload: dict[str, object]) -> None:
    calls_path = os.environ.get("BUDDYSWITCH_TEST_CALLS")
    if not calls_path:
        return
    path = Path(calls_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _read_pid(path: Path) -> int | None:
    try:
        value = int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, OSError, ValueError):
        return None
    return value if value > 0 else None


def _pid_group(pid: int) -> int | None:
    try:
        return os.getpgid(pid)
    except OSError:
        return None


def append_process_registry(payload: dict[str, object]) -> None:
    registry_path = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")
    if not registry_path:
        return
    argv = payload.get("argv")
    if not isinstance(argv, list) or argv[:2] != ["app-server", "--listen"]:
        return
    record: dict[str, object] = {
        "kind": "fake-codex",
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "argv": argv,
        "cwd": payload.get("cwd"),
        "actor_id": payload.get("actor_id"),
        "instance_json": payload.get("instance_json"),
    }
    instance_json = payload.get("instance_json")
    if isinstance(instance_json, str) and instance_json:
        instance_root = Path(instance_json).parent
        record["instance_root"] = str(instance_root)
        for prefix, pid_path in (
            ("runtime_broker", instance_root / "runtime" / "runtime-broker.pid"),
            ("browser", instance_root / "browser" / "chrome.pid"),
        ):
            pid = _read_pid(pid_path)
            if pid is None:
                continue
            record[f"{prefix}_pid"] = pid
            pgid = _pid_group(pid)
            if pgid is not None:
                record[f"{prefix}_pgid"] = pgid
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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
        ["python3", "scripts/turn_runtime.py", "status"],
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
        "python3",
        "scripts/runtime_kernel/broker.py",
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
        "--manifest",
        str(Path(os.getcwd()) / "buddyswitch" / "manifest.toml"),
    ]
    repo_root = entry.get("repo_root")
    if isinstance(repo_root, str) and repo_root:
        status_command.extend(["--repo-root", repo_root])
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
        ("turn_runtime.status", ["python3", "scripts/turn_runtime.py", "status"]),
        ("context.summarize", ["python3", "scripts/env/client.py", "context", "summarize"]),
        ("actor_private.desc", ["python3", "scripts/env/client.py", "actor_private", "desc"]),
        ("search.status", ["python3", "scripts/env/client.py", "search", "status"]),
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


def server_state_path() -> Path | None:
    raw = os.environ.get("BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE")
    if not raw:
        return None
    return Path(raw)


def load_server_state(default_thread_id: str) -> dict[str, object]:
    global MEMORY_STATE
    path = server_state_path()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            state = {"thread_id": default_thread_id}
            path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            return state
        payload = read_json(path)
        if "thread_id" not in payload:
            payload["thread_id"] = default_thread_id
        return payload
    if "thread_id" not in MEMORY_STATE:
        MEMORY_STATE = {"thread_id": default_thread_id}
    return dict(MEMORY_STATE)


def save_server_state(state: dict[str, object]) -> None:
    global MEMORY_STATE
    path = server_state_path()
    if path is not None:
        path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return
    MEMORY_STATE = dict(state)


def _main_thread_id(state: dict[str, object]) -> str:
    return str(state.get("thread_id") or "thread-test")


def _sync_main_thread_legacy(state: dict[str, object]) -> None:
    threads = state.get("threads")
    if not isinstance(threads, dict):
        return
    main_thread = threads.get(_main_thread_id(state))
    if not isinstance(main_thread, dict):
        return
    state["thread_status"] = main_thread.get("status", {"type": "idle"})
    state["turns"] = main_thread.get("turns", [])


def _ensure_threads_state(state: dict[str, object]) -> dict[str, dict[str, object]]:
    main_thread_id = _main_thread_id(state)
    threads = state.get("threads")
    if not isinstance(threads, dict):
        threads = {}
    main_thread = threads.get(main_thread_id)
    if not isinstance(main_thread, dict):
        main_thread = {}
        threads[main_thread_id] = main_thread
    if "status" not in main_thread:
        main_thread["status"] = state.get("thread_status", {"type": "idle"})
    if not isinstance(main_thread.get("turns"), list):
        main_thread["turns"] = state.get("turns", [])
    if not isinstance(main_thread.get("injected_items"), list):
        main_thread["injected_items"] = []
    if "rollout_materialized" not in main_thread:
        main_thread["rollout_materialized"] = bool(main_thread["turns"] or main_thread["injected_items"])
    state["threads"] = threads
    _sync_main_thread_legacy(state)
    return threads


def _thread_state(state: dict[str, object], thread_id: str) -> dict[str, object]:
    threads = _ensure_threads_state(state)
    thread = threads.get(thread_id)
    if not isinstance(thread, dict):
        thread = {
            "status": {"type": "idle"},
            "turns": [],
            "injected_items": [],
            "rollout_materialized": False,
        }
        threads[thread_id] = thread
    if not isinstance(thread.get("turns"), list):
        thread["turns"] = []
    if not isinstance(thread.get("injected_items"), list):
        thread["injected_items"] = []
    if "rollout_materialized" not in thread:
        thread["rollout_materialized"] = bool(thread["turns"] or thread["injected_items"])
    return thread


def _allocate_side_thread_id(state: dict[str, object]) -> str:
    side_thread_id = str(state.get("next_side_thread_id", "thread-side-1"))
    prefix, separator, suffix = side_thread_id.rpartition("-")
    if separator and suffix.isdigit():
        state["next_side_thread_id"] = f"{prefix}-{int(suffix) + 1}"
    return side_thread_id


def default_thread(
    state: dict[str, object],
    *,
    thread_id: str | None = None,
    status: object | None = None,
) -> dict[str, object]:
    actual_thread_id = thread_id or _main_thread_id(state)
    thread_state = _thread_state(state, actual_thread_id)
    thread_status = status if status is not None else thread_state.get("status", {"type": "idle"})
    return {
        "id": actual_thread_id,
        "sessionId": thread_state.get("session_id", state.get("session_id", actual_thread_id)),
        "forkedFromId": thread_state.get("forked_from_id"),
        "preview": "",
        "ephemeral": bool(thread_state.get("ephemeral", False)),
        "modelProvider": "openai",
        "createdAt": 0,
        "updatedAt": 0,
        "status": thread_status,
        "path": None,
        "cwd": thread_state.get("cwd", os.getcwd()),
        "cliVersion": "test",
        "source": "appServer",
        "threadSource": None,
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": None,
        "turns": thread_state.get("turns", []),
    }


def default_turn(turn_id: str, status: str = "inProgress") -> dict[str, object]:
    return {
        "id": turn_id,
        "items": [],
        "itemsView": "summary",
        "status": status,
        "error": None,
        "startedAt": 0,
        "completedAt": None,
        "durationMs": None,
    }


def build_default_result(method: str, params: dict[str, object] | None, state: dict[str, object]) -> dict[str, object]:
    if method == "thread/loaded/list":
        return {"data": list(_ensure_threads_state(state).keys()), "nextCursor": None}
    if method == "thread/start":
        if isinstance(params, dict) and params.get("sessionStartSource") == "clear":
            clear_thread_id = str(state.get("clear_thread_id", "thread-cleared"))
            temp_state = dict(state)
            temp_state["thread_id"] = clear_thread_id
            temp_state["threads"] = {
                **_ensure_threads_state(state),
                clear_thread_id: {
                    "status": {"type": "idle"},
                    "turns": [],
                    "injected_items": [],
                    "rollout_materialized": False,
                },
            }
            return {"thread": default_thread(temp_state, thread_id=clear_thread_id)}
        return {"thread": default_thread(state)}
    if method == "thread/resume":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else _main_thread_id(state)
        thread = default_thread(state, thread_id=thread_id)
        response_thread_id = state.get("thread_resume_response_thread_id")
        if isinstance(response_thread_id, str):
            thread["id"] = response_thread_id
        return {
            "thread": thread,
            "model": "gpt-5",
            "modelProvider": "openai",
            "serviceTier": None,
            "cwd": os.getcwd(),
            "runtimeWorkspaceRoots": [],
            "instructionSources": [],
            "approvalPolicy": "never",
            "approvalsReviewer": "user",
            "sandbox": {"mode": "workspace-write"},
            "activePermissionProfile": {"id": "buddyswitch-runtime"},
            "reasoningEffort": None,
        }
    if method == "thread/fork":
        parent_thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else _main_thread_id(state)
        side_thread_id = str(state.get("next_side_thread_id", "thread-side-1"))
        thread = default_thread(state, thread_id=side_thread_id, status={"type": "idle"})
        thread["forkedFromId"] = parent_thread_id
        thread["ephemeral"] = True
        return {"thread": thread}
    if method == "thread/inject_items":
        return {}
    if method == "thread/read":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else _main_thread_id(state)
        return {"thread": default_thread(state, thread_id=thread_id)}
    if method == "thread/turns/list":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else _main_thread_id(state)
        return {
            "data": _thread_state(state, thread_id).get("turns", []),
            "nextCursor": None,
            "backwardsCursor": None,
        }
    if method == "turn/start":
        next_turn_id = str(state.get("next_turn_id", "turn-test"))
        return {"turn": default_turn(next_turn_id)}
    if method == "turn/steer":
        expected_turn_id = None
        if isinstance(params, dict):
            expected_turn_id = params.get("expectedTurnId")
        return {"turnId": expected_turn_id or state.get("next_turn_id", "turn-test")}
    if method == "turn/interrupt":
        return {}
    if method == "thread/goal/get":
        return {"goal": state.get("goal")}
    if method == "thread/goal/set":
        thread_id = str(params.get("threadId") if isinstance(params, dict) else state.get("thread_id"))
        goal = {
            "threadId": thread_id,
            "objective": params.get("objective") if isinstance(params, dict) and isinstance(params.get("objective"), str) else "",
            "status": params.get("status") if isinstance(params, dict) and isinstance(params.get("status"), str) else "active",
            "tokenBudget": params.get("tokenBudget") if isinstance(params, dict) and isinstance(params.get("tokenBudget"), int) else None,
            "tokensUsed": 0,
            "timeUsedSeconds": 0,
            "createdAt": 0,
            "updatedAt": 0,
        }
        return {"goal": goal}
    if method == "thread/goal/clear":
        return {"cleared": state.get("goal") is not None}
    if method == "thread/compact/start":
        return {}
    return {}


def maybe_mutate_state(method: str, params: dict[str, object] | None, state: dict[str, object]) -> None:
    main_thread_id = _main_thread_id(state)
    if method == "thread/start":
        if isinstance(params, dict) and params.get("sessionStartSource") == "clear":
            state["thread_id"] = str(state.get("clear_thread_id", "thread-cleared"))
            main_thread_id = _main_thread_id(state)
            main_thread = _thread_state(state, main_thread_id)
            main_thread["status"] = {"type": "idle"}
            main_thread["turns"] = []
            main_thread["injected_items"] = []
            main_thread["rollout_materialized"] = False
            _sync_main_thread_legacy(state)
            return
        main_thread = _thread_state(state, main_thread_id)
        if "thread_status" in state or "turns" in state:
            if "thread_status" in state:
                main_thread["status"] = state.get("thread_status", {"type": "idle"})
            if isinstance(state.get("turns"), list):
                main_thread["turns"] = state.get("turns", [])
            main_thread["rollout_materialized"] = bool(main_thread.get("turns") or main_thread.get("injected_items"))
        else:
            main_thread["status"] = {"type": "idle"}
            main_thread["turns"] = []
            main_thread["injected_items"] = []
            main_thread["rollout_materialized"] = False
        _sync_main_thread_legacy(state)
        return
    if method == "thread/resume":
        count = state.get("thread_resume_count")
        state["thread_resume_count"] = (count if isinstance(count, int) else 0) + 1
        if isinstance(params, dict):
            state["last_thread_resume_params"] = dict(params)
        return
    if method == "thread/fork":
        parent_thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else main_thread_id
        side_thread_id = _allocate_side_thread_id(state)
        side_thread = _thread_state(state, side_thread_id)
        side_thread["status"] = {"type": "idle"}
        side_thread["turns"] = []
        side_thread["injected_items"] = []
        side_thread["ephemeral"] = True
        side_thread["forked_from_id"] = parent_thread_id
        return
    if method == "thread/inject_items":
        if not isinstance(params, dict):
            return
        thread_id = str(params.get("threadId") or main_thread_id)
        thread = _thread_state(state, thread_id)
        items = params.get("items")
        if isinstance(items, list):
            thread["injected_items"] = [*thread.get("injected_items", []), *items]
            thread["rollout_materialized"] = True
        return
    if method == "turn/start":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else main_thread_id
        next_turn_id = str(state.get("next_turn_id", "turn-test"))
        thread = _thread_state(state, thread_id)
        thread["status"] = {"type": "active", "activeFlags": []}
        thread["turns"] = [default_turn(next_turn_id)]
        thread["rollout_materialized"] = True
        if thread_id == main_thread_id:
            _sync_main_thread_legacy(state)
        return
    if method == "turn/steer":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else main_thread_id
        thread = _thread_state(state, thread_id)
        turns = thread.get("turns")
        if not isinstance(turns, list) or not turns:
            expected_turn_id = None
            if isinstance(params, dict):
                expected_turn_id = params.get("expectedTurnId")
            thread["turns"] = [default_turn(str(expected_turn_id or state.get("next_turn_id", "turn-test")))]
        thread["status"] = {"type": "active", "activeFlags": []}
        if thread_id == main_thread_id:
            _sync_main_thread_legacy(state)
        return
    if method == "turn/interrupt":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else main_thread_id
        thread = _thread_state(state, thread_id)
        turns = thread.get("turns")
        turn_id = params.get("turnId") if isinstance(params, dict) else None
        if isinstance(turns, list) and turns:
            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                if turn_id in {None, "", turn.get("id")}:
                    turn["status"] = "interrupted"
                    break
        thread["status"] = {"type": "idle"}
        if thread_id == main_thread_id:
            _sync_main_thread_legacy(state)
        return
    if method == "thread/goal/set":
        if not isinstance(params, dict):
            return
        thread_id = str(params.get("threadId") or state.get("thread_id") or "thread-test")
        previous = state.get("goal") if isinstance(state.get("goal"), dict) else {}
        goal = dict(previous)
        goal.update(
            {
                "threadId": thread_id,
                "objective": params.get("objective", goal.get("objective", "")),
                "status": params.get("status", goal.get("status", "active")),
                "tokenBudget": params.get("tokenBudget", goal.get("tokenBudget")),
                "tokensUsed": goal.get("tokensUsed", 0),
                "timeUsedSeconds": goal.get("timeUsedSeconds", 0),
                "createdAt": goal.get("createdAt", 0),
                "updatedAt": 0,
            }
        )
        state["goal"] = goal
        return
    if method == "thread/goal/clear":
        state.pop("goal", None)
        return


def rpc_error_response(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"id": request_id, "error": {"code": code, "message": message}}


def rpc_result_response(request_id: object, result: dict[str, object]) -> dict[str, object]:
    return {"id": request_id, "result": result}


def handle_rpc_message(
    message: dict[str, object],
    entry: dict[str, object],
    *,
    client_name: str = "",
) -> dict[str, object] | None:
    method = message.get("method")
    if not isinstance(method, str):
        return None

    request_id = message.get("id")
    params = message.get("params")
    params_dict = params if isinstance(params, dict) else None
    append_calls(
        {
            "argv": ["json-rpc", method],
            "rpc_method": method,
            "params": params,
            "cwd": os.getcwd(),
            "actor_id": entry.get("actor_id"),
            "client_name": client_name,
        }
    )
    if method == "initialized":
        return None
    if method == "initialize":
        return rpc_result_response(request_id, {"userAgent": "codex/1.0.0"})

    default_thread_id = str(entry.get("actor_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    if method == "thread/resume":
        attempt_count = state.get("thread_resume_attempt_count")
        next_attempt = (attempt_count if isinstance(attempt_count, int) else 0) + 1
        state["thread_resume_attempt_count"] = next_attempt
        if isinstance(params_dict, dict):
            state["last_thread_resume_params"] = dict(params_dict)
        error_on_count = state.get("thread_resume_error_on_count")
        if isinstance(error_on_count, int) and next_attempt == error_on_count:
            save_server_state(state)
            return rpc_error_response(request_id, -32001, "thread/resume failed")
    attempt_counts = state.get("method_attempt_counts")
    if not isinstance(attempt_counts, dict):
        attempt_counts = {}
    previous_attempt = attempt_counts.get(method)
    next_attempt = (previous_attempt if isinstance(previous_attempt, int) else 0) + 1
    attempt_counts[method] = next_attempt
    state["method_attempt_counts"] = attempt_counts
    error_on_attempts = state.get("error_on_attempts")
    if isinstance(error_on_attempts, dict):
        method_attempts = error_on_attempts.get(method)
        if isinstance(method_attempts, dict):
            attempt_error = method_attempts.get(str(next_attempt))
            if isinstance(attempt_error, dict):
                code = attempt_error.get("code")
                message_text = attempt_error.get("message")
                save_server_state(state)
                return rpc_error_response(
                    request_id,
                    code if isinstance(code, int) else -32001,
                    message_text if isinstance(message_text, str) else f"{method} failed",
                )
    errors = state.get("errors", {})
    if isinstance(errors, dict):
        error = errors.get(method)
        if isinstance(error, dict):
            code = error.get("code")
            message_text = error.get("message")
            return rpc_error_response(
                request_id,
                code if isinstance(code, int) else -32001,
                message_text if isinstance(message_text, str) else f"{method} failed",
            )

    if method == "thread/resume":
        thread_id = str(params_dict.get("threadId")) if isinstance(params_dict, dict) and params_dict.get("threadId") else _main_thread_id(state)
        thread = _thread_state(state, thread_id)
        if thread.get("rollout_materialized") is False:
            save_server_state(state)
            return rpc_error_response(request_id, -32600, f"no rollout found for thread id {thread_id}")

    responses = state.get("responses", {})
    if isinstance(responses, dict):
        response = responses.get(method)
        if isinstance(response, dict):
            maybe_mutate_state(method, params_dict, state)
            save_server_state(state)
            return rpc_result_response(request_id, response)

    result = build_default_result(method, params_dict, state)
    maybe_mutate_state(method, params_dict, state)
    save_server_state(state)
    return rpc_result_response(request_id, result)


def read_http_request(sock: socket.socket) -> str:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("client closed before websocket upgrade")
        data += chunk
    return data.decode("ascii")


def websocket_accept_value(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")


def extract_websocket_key(headers: str) -> str:
    for line in headers.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("missing Sec-WebSocket-Key")


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed")
        data += chunk
    return data


def read_frame(sock: socket.socket) -> tuple[int, bytes]:
    first, second = read_exact(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(read_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(sock, 8), "big")
    mask = read_exact(sock, 4) if masked else b""
    payload = read_exact(sock, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def send_frame(sock: socket.socket, opcode: int, payload: bytes) -> None:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    sock.sendall(header + payload)


def send_json(sock: socket.socket, payload: dict[str, object]) -> None:
    send_frame(sock, 0x1, json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def _daemon_notifications(entry: dict[str, object]) -> list[dict[str, object]]:
    default_thread_id = str(entry.get("actor_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    notifications = state.get("daemon_notifications")
    if not isinstance(notifications, list):
        return []
    return [notification for notification in notifications if isinstance(notification, dict)]


def send_daemon_notifications(sock: socket.socket, entry: dict[str, object], *, client_name: str) -> None:
    for notification in _daemon_notifications(entry):
        append_calls(
            {
                "argv": ["daemon-notification"],
                "kind": "daemon-notification",
                "notification_method": notification.get("method"),
                "params": notification.get("params"),
                "cwd": os.getcwd(),
                "actor_id": entry.get("actor_id"),
                "client_name": client_name,
            }
        )
        send_json(sock, notification)


def send_daemon_started_turn_completion(
    sock: socket.socket,
    entry: dict[str, object],
    request: dict[str, object],
    response: dict[str, object] | None,
    *,
    client_name: str,
) -> None:
    if request.get("method") != "turn/start" or response is None:
        return
    default_thread_id = str(entry.get("actor_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    if not state.get("daemon_emit_completion_for_started_turn"):
        return
    subscribed_thread_id = state.get("daemon_subscribed_thread_id")
    if not isinstance(subscribed_thread_id, str) or not subscribed_thread_id:
        return
    result = response.get("result")
    turn = result.get("turn") if isinstance(result, dict) else None
    turn_id = turn.get("id") if isinstance(turn, dict) else None
    params = request.get("params")
    thread_id = params.get("threadId") if isinstance(params, dict) else None
    if not isinstance(turn_id, str) or not turn_id:
        return
    if not isinstance(thread_id, str) or not thread_id:
        thread_id = subscribed_thread_id
    notification = {
        "method": "turn/completed",
        "params": {
            "threadId": thread_id,
            "turn": {
                "id": turn_id,
                "items": [],
                "itemsView": "summary",
                "status": "completed",
                "error": None,
                "startedAt": 0,
                "completedAt": 1,
                "durationMs": 1,
            },
        },
    }
    append_calls(
        {
            "argv": ["daemon-notification"],
            "kind": "daemon-notification",
            "notification_method": notification.get("method"),
            "params": notification.get("params"),
            "cwd": os.getcwd(),
            "actor_id": entry.get("actor_id"),
            "client_name": client_name,
        }
    )
    send_json(sock, notification)


def handle_websocket_connection(sock: socket.socket, entry: dict[str, object]) -> None:
    sock.settimeout(0.5)
    headers = read_http_request(sock)
    websocket_key = extract_websocket_key(headers)
    client_name = ""
    sock.sendall(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {websocket_accept_value(websocket_key)}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    while RUNNING:
        try:
            opcode, payload = read_frame(sock)
        except (TimeoutError, socket.timeout):
            continue
        except (EOFError, OSError):
            return
        if opcode == 0x1:
            message = json.loads(payload.decode("utf-8"))
            if not isinstance(message, dict):
                continue
            method = message.get("method")
            if method == "initialize":
                params = message.get("params")
                client_info = params.get("clientInfo") if isinstance(params, dict) else None
                name = client_info.get("name") if isinstance(client_info, dict) else None
                if isinstance(name, str):
                    client_name = name
            response = handle_rpc_message(message, entry, client_name=client_name)
            if response is not None:
                send_json(sock, response)
            if (
                client_name == "buddyswitch_daemon"
                and method == "thread/resume"
                and isinstance(response, dict)
                and "result" in response
            ):
                params = message.get("params")
                thread_id = params.get("threadId") if isinstance(params, dict) else None
                if isinstance(thread_id, str) and thread_id:
                    default_thread_id = str(entry.get("actor_id") or "thread-test")
                    state = load_server_state(f"thread-{default_thread_id}")
                    state["daemon_subscribed_thread_id"] = thread_id
                    save_server_state(state)
                send_daemon_notifications(sock, entry, client_name=client_name)
            if client_name == "buddyswitch_daemon":
                send_daemon_started_turn_completion(sock, entry, message, response, client_name=client_name)
        elif opcode == 0x8:
            try:
                send_frame(sock, 0x8, payload)
            except OSError:
                pass
            return
        elif opcode == 0x9:
            try:
                send_frame(sock, 0xA, payload)
            except OSError:
                return
        elif opcode == 0xA:
            continue


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
            handle_websocket_connection(client, entry)
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
        "repo_root": os.environ.get("BUDDYSWITCH_REPO_ROOT"),
        "actor_private_dir": os.environ.get("BUDDYSWITCH_ACTOR_PRIVATE_DIR"),
        "instance_tmp": os.environ.get("BUDDYSWITCH_INSTANCE_TMP"),
        "project_workspace_dir": os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR"),
        "runtime_broker_socket": os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_SOCKET"),
    }
    append_calls(entry)
    append_process_registry(entry)

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
