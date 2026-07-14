"""JSON-RPC behavior for the fake Codex app server."""

from __future__ import annotations

import os

from .state import (
    allocate_side_thread_id as _allocate_side_thread_id,
    append_calls,
    default_thread,
    default_turn,
    ensure_threads_state as _ensure_threads_state,
    load_server_state,
    main_thread_id as _main_thread_id,
    save_server_state,
    sync_main_thread_legacy as _sync_main_thread_legacy,
    thread_state as _thread_state,
)


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
    primary_thread_id = _main_thread_id(state)
    if method == "thread/start":
        if isinstance(params, dict) and params.get("sessionStartSource") == "clear":
            state["thread_id"] = str(state.get("clear_thread_id", "thread-cleared"))
            primary_thread_id = _main_thread_id(state)
            main_thread = _thread_state(state, primary_thread_id)
            main_thread["status"] = {"type": "idle"}
            main_thread["turns"] = []
            main_thread["injected_items"] = []
            main_thread["rollout_materialized"] = False
            _sync_main_thread_legacy(state)
            return
        main_thread = _thread_state(state, primary_thread_id)
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
        parent_thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else primary_thread_id
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
        thread_id = str(params.get("threadId") or primary_thread_id)
        thread = _thread_state(state, thread_id)
        items = params.get("items")
        if isinstance(items, list):
            thread["injected_items"] = [*thread.get("injected_items", []), *items]
            thread["rollout_materialized"] = True
        return
    if method == "turn/start":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else primary_thread_id
        next_turn_id = str(state.get("next_turn_id", "turn-test"))
        thread = _thread_state(state, thread_id)
        thread["status"] = {"type": "active", "activeFlags": []}
        thread["turns"] = [default_turn(next_turn_id)]
        thread["rollout_materialized"] = True
        if thread_id == primary_thread_id:
            _sync_main_thread_legacy(state)
        return
    if method == "turn/steer":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else primary_thread_id
        thread = _thread_state(state, thread_id)
        turns = thread.get("turns")
        if not isinstance(turns, list) or not turns:
            expected_turn_id = params.get("expectedTurnId") if isinstance(params, dict) else None
            thread["turns"] = [default_turn(str(expected_turn_id or state.get("next_turn_id", "turn-test")))]
        thread["status"] = {"type": "active", "activeFlags": []}
        if thread_id == primary_thread_id:
            _sync_main_thread_legacy(state)
        return
    if method == "turn/interrupt":
        thread_id = str(params.get("threadId")) if isinstance(params, dict) and params.get("threadId") else primary_thread_id
        thread = _thread_state(state, thread_id)
        turns = thread.get("turns")
        turn_id = params.get("turnId") if isinstance(params, dict) else None
        if isinstance(turns, list) and turns:
            for turn in turns:
                if isinstance(turn, dict) and turn_id in {None, "", turn.get("id")}:
                    turn["status"] = "interrupted"
                    break
        thread["status"] = {"type": "idle"}
        if thread_id == primary_thread_id:
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
    if method == "thread/turns/list":
        thread_id = str(params_dict.get("threadId")) if isinstance(params_dict, dict) and params_dict.get("threadId") else _main_thread_id(state)
        if _thread_state(state, thread_id).get("ephemeral") is True:
            save_server_state(state)
            return rpc_error_response(
                request_id,
                -32600,
                f"thread/turns/list is unavailable for ephemeral thread {thread_id}",
            )

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
