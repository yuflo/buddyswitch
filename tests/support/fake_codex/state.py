"""Persistent and in-memory state for the fake Codex app server."""

from __future__ import annotations

import json
import os
from pathlib import Path


MEMORY_STATE: dict[str, object] = {}


def append_calls(payload: dict[str, object]) -> None:
    calls_path = os.environ.get("BUDDYSWITCH_TEST_CALLS")
    if not calls_path:
        return
    path = Path(calls_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def main_thread_id(state: dict[str, object]) -> str:
    return str(state.get("thread_id") or "thread-test")


def sync_main_thread_legacy(state: dict[str, object]) -> None:
    threads = state.get("threads")
    if not isinstance(threads, dict):
        return
    main_thread = threads.get(main_thread_id(state))
    if not isinstance(main_thread, dict):
        return
    state["thread_status"] = main_thread.get("status", {"type": "idle"})
    state["turns"] = main_thread.get("turns", [])


def ensure_threads_state(state: dict[str, object]) -> dict[str, dict[str, object]]:
    primary_thread_id = main_thread_id(state)
    threads = state.get("threads")
    if not isinstance(threads, dict):
        threads = {}
    main_thread = threads.get(primary_thread_id)
    if not isinstance(main_thread, dict):
        main_thread = {}
        threads[primary_thread_id] = main_thread
    if "status" not in main_thread:
        main_thread["status"] = state.get("thread_status", {"type": "idle"})
    if not isinstance(main_thread.get("turns"), list):
        main_thread["turns"] = state.get("turns", [])
    if not isinstance(main_thread.get("injected_items"), list):
        main_thread["injected_items"] = []
    if "rollout_materialized" not in main_thread:
        main_thread["rollout_materialized"] = bool(main_thread["turns"] or main_thread["injected_items"])
    state["threads"] = threads
    sync_main_thread_legacy(state)
    return threads


def thread_state(state: dict[str, object], thread_id: str) -> dict[str, object]:
    threads = ensure_threads_state(state)
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


def allocate_side_thread_id(state: dict[str, object]) -> str:
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
    actual_thread_id = thread_id or main_thread_id(state)
    current_thread = thread_state(state, actual_thread_id)
    thread_status = status if status is not None else current_thread.get("status", {"type": "idle"})
    return {
        "id": actual_thread_id,
        "sessionId": current_thread.get("session_id", state.get("session_id", actual_thread_id)),
        "forkedFromId": current_thread.get("forked_from_id"),
        "preview": "",
        "ephemeral": bool(current_thread.get("ephemeral", False)),
        "modelProvider": "openai",
        "createdAt": 0,
        "updatedAt": 0,
        "status": thread_status,
        "path": None,
        "cwd": current_thread.get("cwd", os.getcwd()),
        "cliVersion": "test",
        "source": "appServer",
        "threadSource": None,
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": None,
        "turns": current_thread.get("turns", []),
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
