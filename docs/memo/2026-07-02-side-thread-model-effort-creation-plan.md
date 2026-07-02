# Side-Thread Model And Effort Creation Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a side-thread creation contract that accepts optional `model` and `effort` overrides for the new side thread only, while `None` means inherit the parent thread model settings and no local or global model configuration is persisted.

**Architecture:** `side_thread_lifecycle` remains the only BuddySwitch owner that composes side-thread lifecycle operations. Interfaces such as Web and CLI only validate and forward creation intent; `app_server.thread_fork` remains a primitive Codex RPC adapter and serializes creation-time overrides into `thread/fork`. No caller may route this through `/model`, `thread/settings/update`, `config/batchWrite`, or registry-driven model state.

**Tech Stack:** Python launcher modules under `tools/launcher/`, shell entrypoints in `buddyswitch-codex` and `tools/launcher/env.sh`, HTTP control-plane tests under `tests/test_web_management.py`, launcher integration tests under `tests/test_buddyswitch_launcher.py`, focused `unittest` suites, and Codex app-server JSON-RPC `thread/fork` params.

---

## Re-Focused Task Target

The basic target is not "change the current model" and not "remember a preferred side model".

The target is:

```text
create side-thread request
  -> optional model override
  -> optional reasoning effort override
  -> thread/fork creates the child side-thread with those overrides
  -> parent-thread model and effort remain untouched
  -> no local config or registry persistence records the model choice
```

Default behavior is also part of the contract:

```text
model=None  -> do not send a model field to thread/fork; Codex inherits from parent thread metadata
effort=None -> do not send config.model_reasoning_effort to thread/fork; Codex inherits from parent thread metadata
```

This must be implemented as forward replacement at the existing lifecycle boundary, not as a compatibility path beside it.

## Current Code Findings

- `tools/launcher/side_thread_lifecycle.py` is now the concrete lifecycle owner. `start_side_thread()` composes fork, boundary injection, turn start, and lease registration.
- `tools/launcher/app_server.py::thread_fork()` is the only production primitive that sends `thread/fork`.
- `tools/launcher/task_sys_runtime.py` delegates Task Sys side-frame creation to `side_thread_lifecycle.start_side_thread()`.
- `tools/launcher/daemon_core.py` delegates daemon side triage to `side_thread_lifecycle.find_or_start_side_thread()`.
- `buddyswitch-codex instance side` routes host-control side start/send through `buddyswitch_side_thread_lifecycle_start` and `buddyswitch_side_thread_lifecycle_send`.
- `tests/test_repo_consistency.py::test_side_thread_lifecycle_boundary_has_no_direct_call_residue` scans for direct Python app-server plus registry lifecycle composition outside the lifecycle owner.
- `tools/launcher/env.sh` still exposes direct shell helpers named `buddyswitch_instance_register_side_thread`, `buddyswitch_instance_require_side_thread`, and `buddyswitch_instance_unregister_side_thread`. They are not used by current `instance side`, but they are live helper surfaces and should be removed or covered by a stronger residue scan in the same change set.

## Non-Negotiable Requirements

- `model` and `effort` are side-thread creation parameters only.
- `None` means inherit parent thread settings by omitting the corresponding `thread/fork` field.
- Empty or whitespace-only `model` and `effort` are invalid when provided.
- Existing side-thread send paths reject `model` or `effort` instead of ignoring them.
- No BuddySwitch code writes `model`, `model_reasoning_effort`, or side model metadata to local config.
- No BuddySwitch code uses `/model`, `thread/settings/update`, `config/batchWrite`, or Codex TUI model persistence for this feature.
- `side_thread_registry` does not store model or effort.
- Web and CLI are projections. They validate request shape and pass values to the lifecycle owner; they do not own model policy.
- Task Sys and daemon runtime remain optional policy owners. If either later chooses a model for its own side-thread class, it must pass explicit values into `side_thread_lifecycle`, not bypass the lifecycle owner.
- The implementation must include behavior tests and live-surface residue checks. A passing local unit test without residue proof is not enough.

## End-To-End Contract Slice

Use this as the acceptance sentence:

```text
Web or CLI user starts a new side-thread with model and effort
  -> BuddySwitch passes those values through host-control projections into side_thread_lifecycle
  -> side_thread_lifecycle calls app_server.thread_fork once with model and config.model_reasoning_effort
  -> the new side-thread starts normally and registers a lease
  -> no parent-thread settings update, config write, or registry model field occurs
```

Negative contract:

```text
Web or CLI user sends to an existing side-thread while also providing model or effort
  -> BuddySwitch rejects the request before RPC mutation
  -> no thread/fork, turn/start, turn/steer, thread/settings/update, or config/batchWrite occurs
```

## File Map

Modify:

- `tools/launcher/app_server.py`
  - Add optional `model` and `model_reasoning_effort` parameters to `thread_fork()`.
  - Serialize only non-`None` values into `thread/fork`.

- `tools/launcher/side_thread_lifecycle.py`
  - Add optional `model` and `model_reasoning_effort` parameters to `start_side_thread()` and `find_or_start_side_thread()`.
  - Reject ignored overrides when `find_or_start_side_thread()` would reuse an existing side-thread.
  - Add CLI flags for `start` only.

- `tools/launcher/env.sh`
  - Pass optional model and effort from shell helper to lifecycle CLI.
  - Remove direct registry shell helpers after confirming no live caller uses them.

- `buddyswitch-codex`
  - Add `instance side --model <model> --effort <effort>` for creation.
  - Reject `--model` or `--effort` when `--side-thread-id` is present.

- `tools/launcher/web_management.py`
  - Accept optional JSON fields `model` and `effort` on side start.
  - Reject `model` or `effort` when `side_thread_id` is present.
  - Pass creation overrides to the CLI command only for new side-thread creation.

- `tools/launcher/task_sys_runtime.py`
  - Keep current `None` behavior unless there is an explicit Task Sys side model source in context. No hidden defaults.

Test:

- `tests/test_app_server_client.py`
- `tests/test_side_thread_lifecycle.py`
- `tests/test_web_management.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_task_sys_runtime_executor.py`
- `tests/test_daemon_service_contract.py`
- `tests/test_repo_consistency.py`

Do not modify:

- `buddyswitch/objects/**`
- `buddyswitch/local/private/**`
- local Codex config files
- `side_thread_registry.py` data shape for model or effort

## Task 1: Pin `thread_fork` Override Serialization

**Files:**

- Modify: `tests/test_app_server_client.py`
- Modify: `tools/launcher/app_server.py`

- [ ] **Step 1: Add a focused app-server client test for explicit overrides**

Add this test to the existing app-server client test class that already uses `FakeUnixWebSocketServer`:

```python
def test_thread_fork_sends_model_and_reasoning_effort_overrides(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        socket_path = self._socket_path(Path(temp_root))
        server = FakeUnixWebSocketServer(socket_path)
        server.start()
        self.addCleanup(server.close)
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def run_fork() -> None:
            try:
                results.append(
                    APP_SERVER.thread_fork(
                        socket_path,
                        "thread-parent",
                        workspace_dir=Path("/tmp/bs-workspace"),
                        shared_project_workspace_dir=Path("/tmp/bs-project"),
                        permissions="buddyswitch-runtime",
                        model="gpt-5.4",
                        model_reasoning_effort="high",
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        fork_thread = threading.Thread(target=run_fork, daemon=True)
        fork_thread.start()

        init = server.next_message()
        self.assertEqual(init["method"], "initialize")
        server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
        self.assertEqual(server.next_message()["method"], "initialized")

        request = server.next_message()
        self.assertEqual(request["method"], "thread/fork")
        params = request["params"]
        assert isinstance(params, dict)
        self.assertEqual(params["threadId"], "thread-parent")
        self.assertEqual(params["model"], "gpt-5.4")
        self.assertEqual(params["config"], {"model_reasoning_effort": "high"})
        self.assertEqual(params["permissions"], "buddyswitch-runtime")
        self.assertTrue(params["ephemeral"])
        self.assertTrue(params["excludeTurns"])

        server.send_response(
            request["id"],
            {
                "thread": {"id": "thread-side-1", "status": {"type": "idle"}},
                "model": "gpt-5.4",
                "modelProvider": "openai",
                "serviceTier": None,
                "cwd": "/tmp/bs-workspace",
                "runtimeWorkspaceRoots": ["/tmp/bs-workspace", "/tmp/bs-project"],
                "instructionSources": [],
                "approvalPolicy": "never",
                "approvalsReviewer": "user",
                "sandbox": {"mode": "workspace-write"},
                "activePermissionProfile": {"id": "buddyswitch-runtime"},
                "reasoningEffort": "high",
            },
        )
        fork_thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(results[0]["thread"]["id"], "thread-side-1")
```

- [ ] **Step 2: Add a focused app-server client test for inherited defaults**

Add this test next to the explicit override test:

```python
def test_thread_fork_omits_model_and_effort_when_inheriting_parent(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        socket_path = self._socket_path(Path(temp_root))
        server = FakeUnixWebSocketServer(socket_path)
        server.start()
        self.addCleanup(server.close)
        errors: list[BaseException] = []

        def run_fork() -> None:
            try:
                APP_SERVER.thread_fork(
                    socket_path,
                    "thread-parent",
                    workspace_dir=Path("/tmp/bs-workspace"),
                    shared_project_workspace_dir=Path("/tmp/bs-project"),
                    permissions="buddyswitch-runtime",
                )
            except BaseException as exc:
                errors.append(exc)

        fork_thread = threading.Thread(target=run_fork, daemon=True)
        fork_thread.start()

        init = server.next_message()
        self.assertEqual(init["method"], "initialize")
        server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
        self.assertEqual(server.next_message()["method"], "initialized")

        request = server.next_message()
        self.assertEqual(request["method"], "thread/fork")
        params = request["params"]
        assert isinstance(params, dict)
        self.assertNotIn("model", params)
        self.assertNotIn("modelProvider", params)
        self.assertNotIn("config", params)

        server.send_response(
            request["id"],
            {
                "thread": {"id": "thread-side-1", "status": {"type": "idle"}},
                "model": "gpt-5",
                "modelProvider": "openai",
                "serviceTier": None,
                "cwd": "/tmp/bs-workspace",
                "runtimeWorkspaceRoots": ["/tmp/bs-workspace", "/tmp/bs-project"],
                "instructionSources": [],
                "approvalPolicy": "never",
                "approvalsReviewer": "user",
                "sandbox": {"mode": "workspace-write"},
                "activePermissionProfile": {"id": "buddyswitch-runtime"},
                "reasoningEffort": None,
            },
        )
        fork_thread.join(timeout=2)

        self.assertEqual(errors, [])
```

- [ ] **Step 3: Run the new focused tests red**

Run:

```bash
python -m unittest -q tests.test_app_server_client
```

Expected before implementation: failures indicating `thread_fork()` does not accept `model` or `model_reasoning_effort`.

- [ ] **Step 4: Implement the primitive request serialization**

Change `tools/launcher/app_server.py::thread_fork()` to this shape:

```python
def _optional_non_empty_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AppServerProtocolError(f"{field_name} must not be empty")
    return value.strip()


def thread_fork(
    socket_path: Path,
    parent_thread_id: str,
    *,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    if not permissions:
        raise AppServerProtocolError("side fork requires an explicit permissions profile")
    normalized_model = _optional_non_empty_text(model, "model")
    normalized_effort = _optional_non_empty_text(model_reasoning_effort, "model_reasoning_effort")
    params: dict[str, Any] = {
        "threadId": parent_thread_id,
        "cwd": str(workspace_dir),
        "runtimeWorkspaceRoots": [
            str(workspace_dir),
            str(shared_project_workspace_dir),
        ],
        "permissions": permissions,
        "developerInstructions": SIDE_DEVELOPER_INSTRUCTIONS,
        "ephemeral": True,
        "excludeTurns": True,
    }
    if normalized_model is not None:
        params["model"] = normalized_model
    if normalized_effort is not None:
        params["config"] = {"model_reasoning_effort": normalized_effort}
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        return client.request("thread/fork", params)
```

- [ ] **Step 5: Run the focused app-server tests green**

Run:

```bash
python -m unittest -q tests.test_app_server_client
```

Expected: app-server client tests pass.

## Task 2: Make `side_thread_lifecycle` The Public Creation Owner

**Files:**

- Modify: `tests/test_side_thread_lifecycle.py`
- Modify: `tools/launcher/side_thread_lifecycle.py`

- [ ] **Step 1: Extend the fake app-server signature in lifecycle tests**

Update `FakeAppServer.thread_fork()` in `tests/test_side_thread_lifecycle.py`:

```python
def thread_fork(
    self,
    socket_path: Path,
    parent_thread_id: str,
    *,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, object]:
    self.calls.append(
        {
            "helper": "thread_fork",
            "socket_path": socket_path,
            "parent_thread_id": parent_thread_id,
            "workspace_dir": workspace_dir,
            "shared_project_workspace_dir": shared_project_workspace_dir,
            "permissions": permissions,
            "model": model,
            "model_reasoning_effort": model_reasoning_effort,
        }
    )
    return {"thread": {"id": "thr-side-1"}}
```

- [ ] **Step 2: Add lifecycle test for explicit creation overrides**

Add this test:

```python
def test_start_side_thread_passes_model_and_effort_to_fork_without_registry_persistence(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance_json = self._instance_json(temp_root)

        result = self.lifecycle.start_side_thread(
            socket_path=self.socket_path,
            instance_json=instance_json,
            actor_id="act-dev-side",
            parent_thread_id="thr-main",
            text="Start side work",
            purpose="host_control.side",
            workspace_dir=self.workspace_dir,
            shared_project_workspace_dir=self.project_workspace_dir,
            permissions="buddyswitch-runtime",
            model="gpt-5.4",
            model_reasoning_effort="high",
        )

        fork_call = self.app_server.calls[0]
        self.assertEqual(fork_call["helper"], "thread_fork")
        self.assertEqual(fork_call["model"], "gpt-5.4")
        self.assertEqual(fork_call["model_reasoning_effort"], "high")
        self.assertEqual(result["model_source"], "override")
        self.assertEqual(result["model"], "gpt-5.4")
        self.assertEqual(result["model_reasoning_effort_source"], "override")
        self.assertEqual(result["model_reasoning_effort"], "high")

        row = self._payload(instance_json)["side_threads"][0]
        self.assertNotIn("model", row)
        self.assertNotIn("model_reasoning_effort", row)
```

- [ ] **Step 3: Add lifecycle test for inherited defaults**

Add this test:

```python
def test_start_side_thread_none_model_and_effort_mean_parent_inheritance(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance_json = self._instance_json(temp_root)

        result = self.lifecycle.start_side_thread(
            socket_path=self.socket_path,
            instance_json=instance_json,
            actor_id="act-dev-side",
            parent_thread_id="thr-main",
            text="Start side work",
            purpose="host_control.side",
            workspace_dir=self.workspace_dir,
            shared_project_workspace_dir=self.project_workspace_dir,
            permissions="buddyswitch-runtime",
        )

        fork_call = self.app_server.calls[0]
        self.assertIsNone(fork_call["model"])
        self.assertIsNone(fork_call["model_reasoning_effort"])
        self.assertEqual(result["model_source"], "parent_thread")
        self.assertEqual(result["model_reasoning_effort_source"], "parent_thread")
        self.assertNotIn("model", result)
        self.assertNotIn("model_reasoning_effort", result)
```

- [ ] **Step 4: Add lifecycle test rejecting ignored overrides on reuse**

Add this test:

```python
def test_find_or_start_rejects_model_or_effort_when_existing_side_thread_would_be_reused(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance_json = self._instance_json(temp_root)
        self._seed_side_thread(instance_json)

        with self.assertRaisesRegex(self.lifecycle.SideThreadLifecycleError, "only applies when starting a new side thread"):
            self.lifecycle.find_or_start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Follow up",
                purpose="daemon.side_triage",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
                model="gpt-5.4",
            )

        self.assertEqual(self.app_server.calls, [])
```

- [ ] **Step 5: Run lifecycle tests red**

Run:

```bash
python -m unittest -q tests.test_side_thread_lifecycle
```

Expected before implementation: failures for missing parameters and missing response fields.

- [ ] **Step 6: Implement lifecycle parameters and response facts**

Add helpers and parameters:

```python
def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SideThreadLifecycleError(f"{field_name} must not be empty")
    return value.strip()


def _model_config_result(model: str | None, model_reasoning_effort: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_source": "override" if model is not None else "parent_thread",
        "model_reasoning_effort_source": "override" if model_reasoning_effort is not None else "parent_thread",
        "model_config_durability": "thread_fork_only",
    }
    if model is not None:
        payload["model"] = model
    if model_reasoning_effort is not None:
        payload["model_reasoning_effort"] = model_reasoning_effort
    return payload
```

Change `start_side_thread()`:

```python
def start_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    task_id: str | None = None,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    normalized_actor = _require_text(actor_id, "actor_id")
    normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
    normalized_purpose = _require_text(purpose, "purpose")
    normalized_model = _optional_text(model, "model")
    normalized_effort = _optional_text(model_reasoning_effort, "model_reasoning_effort")
    forked = app_server.thread_fork(
        socket_path,
        normalized_parent,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        model=normalized_model,
        model_reasoning_effort=normalized_effort,
    )
    side_thread_id = _thread_id_from_fork(forked)
    app_server.thread_inject_items(socket_path, side_thread_id, [app_server.side_boundary_prompt_item()])
    sent = app_server.turn_start(socket_path, side_thread_id, text, permissions)
    turn_id = _turn_id_from_result(sent)
    side_thread_registry.register_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=side_thread_id,
        task_id=task_id,
        purpose=normalized_purpose,
        turn_id=turn_id,
    )
    return {
        "action": "start",
        "purpose": normalized_purpose,
        "parent_thread_id": normalized_parent,
        "side_thread_id": side_thread_id,
        "thread_action": sent.get("action") or "start",
        "turn_id": turn_id,
        "lease_registered": True,
        **_model_config_result(normalized_model, normalized_effort),
    }
```

Change `find_or_start_side_thread()` to accept the same two optional values. Before sending to an existing side-thread, reject non-`None` values:

```python
normalized_model = _optional_text(model, "model")
normalized_effort = _optional_text(model_reasoning_effort, "model_reasoning_effort")
if isinstance(side_thread_id, str) and side_thread_id.strip():
    if normalized_model is not None or normalized_effort is not None:
        raise SideThreadLifecycleError("model and effort only applies when starting a new side thread")
    return send_to_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        side_thread_id=side_thread_id,
        text=text,
        permissions=permissions,
    )
```

Pass the normalized values into the final `start_side_thread` call in `find_or_start_side_thread`.

- [ ] **Step 7: Add lifecycle CLI start flags**

Change `_command_start()` and parser setup:

```python
model_reasoning_effort=args.effort,
```

```python
start.add_argument("--model")
start.add_argument("--effort")
```

Do not add these flags to `send` or `cleanup`.

- [ ] **Step 8: Run lifecycle tests green**

Run:

```bash
python -m unittest -q tests.test_side_thread_lifecycle
```

Expected: lifecycle tests pass.

## Task 3: Expose Host-Control CLI Creation Parameters Without Send-Time Switching

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`

- [ ] **Step 1: Add launcher integration test for CLI side start overrides**

Add a test near existing `instance side` tests:

```python
def test_side_start_accepts_model_and_effort_as_thread_fork_only_overrides(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home))
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

        Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
        side_result = subprocess.run(
            [
                str(LAUNCHER),
                "instance",
                "side",
                ctx["actor_id"],
                "--text",
                "Use a specific side model",
                "--model",
                "gpt-5.4",
                "--effort",
                "high",
                "--json",
            ],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
        payload = json.loads(side_result.stdout)
        self.assertEqual(payload["action"], "start")
        self.assertEqual(payload["model"], "gpt-5.4")
        self.assertEqual(payload["model_reasoning_effort"], "high")
        self.assertEqual(payload["model_config_durability"], "thread_fork_only")

        rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
        fork = next(row for row in rpc_rows if row["rpc_method"] == "thread/fork")
        self.assertEqual(fork["params"]["model"], "gpt-5.4")
        self.assertEqual(fork["params"]["config"], {"model_reasoning_effort": "high"})
        self.assertNotIn("thread/settings/update", [row["rpc_method"] for row in rpc_rows])
        self.assertNotIn("config/batchWrite", [row["rpc_method"] for row in rpc_rows])
```

- [ ] **Step 2: Add launcher integration test rejecting send-time model changes**

Add this test:

```python
def test_side_send_rejects_model_and_effort_before_rpc_mutation(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home))
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

        main_thread_id = str(ctx["instance_payload"]["thread_id"])
        self._set_instance_side_threads(
            ctx["instance_root"],
            [{"thread_id": "thread-side-1", "parent_thread_id": main_thread_id, "status": "open", "turn_id": "turn-side-1"}],
        )
        Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

        side_result = subprocess.run(
            [
                str(LAUNCHER),
                "instance",
                "side",
                ctx["actor_id"],
                "--side-thread-id",
                "thread-side-1",
                "--text",
                "Bad switch",
                "--model",
                "gpt-5.4",
                "--effort",
                "high",
            ],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(side_result.returncode, 0)
        self.assertIn("only applies when starting a new side thread", side_result.stderr)
        rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
        self.assertEqual(rpc_rows, [])
```

- [ ] **Step 3: Run launcher tests red for the new behavior**

Run the focused launcher test class or file:

```bash
python -m unittest -q tests.test_buddyswitch_launcher
```

Expected before implementation: unknown option failures for `--model` or `--effort`.

- [ ] **Step 4: Update shell lifecycle helper**

Change `buddyswitch_side_thread_lifecycle_start()` in `tools/launcher/env.sh`:

```bash
buddyswitch_side_thread_lifecycle_start() {
  local actor_id="$1"
  local parent_thread_id="$2"
  local text="$3"
  local model="${4:-}"
  local effort="${5:-}"
  local instance_json args

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  args=(
    "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/side_thread_lifecycle.py"
    start
    --socket "$(buddyswitch_app_server_socket)"
    --instance-json "${instance_json}"
    --actor-id "${actor_id}"
    --parent-thread-id "${parent_thread_id}"
    --text "${text}"
    --purpose "host_control.side"
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}"
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
    --permissions "buddyswitch-runtime"
  )
  if [[ -n "${model}" ]]; then
    args+=(--model "${model}")
  fi
  if [[ -n "${effort}" ]]; then
    args+=(--effort "${effort}")
  fi
  python3 "${args[@]}"
}
```

- [ ] **Step 5: Remove direct registry shell helpers**

Delete these functions from `tools/launcher/env.sh`:

```bash
buddyswitch_instance_register_side_thread()
buddyswitch_instance_require_side_thread()
buddyswitch_instance_unregister_side_thread()
```

The current repo search shows no live caller. Removing them prevents shell surfaces from teaching pre-lifecycle registry composition.

- [ ] **Step 6: Update `instance_side()` argument parsing**

Change `buddyswitch-codex::instance_side()` local variables:

```bash
local actor_id="${1:-}" text="" side_thread_id="" parent_thread_id="" model="" effort="" arg output json=0
```

Add cases:

```bash
      --model)
        if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
          echo "instance side requires --model <model>" >&2
          return 2
        fi
        model="$2"
        shift 2
        ;;
      --effort)
        if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
          echo "instance side requires --effort <effort>" >&2
          return 2
        fi
        effort="$2"
        shift 2
        ;;
```

Reject send-time overrides immediately after validating `text`:

```bash
  if [[ -n "${side_thread_id}" && ( -n "${model}" || -n "${effort}" ) ]]; then
    echo "instance side --model/--effort only applies when starting a new side thread" >&2
    return 2
  fi
```

Pass overrides only on start:

```bash
output="$(buddyswitch_side_thread_lifecycle_start "${actor_id}" "${parent_thread_id}" "${text}" "${model}" "${effort}" 2>&1)" || {
```

- [ ] **Step 7: Include model facts in JSON start result**

Update `instance_side_print_start_result()` so it preserves these optional fields from lifecycle output:

```python
for key in ("model", "model_reasoning_effort", "model_source", "model_reasoning_effort_source", "model_config_durability"):
    value = source.get(key)
    if isinstance(value, str) and value:
        payload[key] = value
```

- [ ] **Step 8: Run launcher tests green**

Run:

```bash
python -m unittest -q tests.test_buddyswitch_launcher
```

Expected: launcher tests pass.

## Task 4: Expose Web Creation Parameters As DTO Pass-Through Only

**Files:**

- Modify: `tests/test_web_management.py`
- Modify: `tools/launcher/web_management.py`

- [ ] **Step 1: Add Web side start pass-through test**

Add this test near the existing side route tests:

```python
def test_side_route_passes_model_and_effort_only_for_new_side_thread(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                [
                    "instance",
                    "side",
                    "act-pm-demo",
                    "--text",
                    "Start side",
                    "--model",
                    "gpt-5.4",
                    "--effort",
                    "high",
                    "--json",
                ],
                command_json(
                    {
                        "actor_id": "act-pm-demo",
                        "action": "start",
                        "thread_action": "start",
                        "parent_thread_id": "thread-main",
                        "side_thread_id": "thread-side-1",
                        "turn_id": "turn-side-1",
                        "model": "gpt-5.4",
                        "model_reasoning_effort": "high",
                        "model_source": "override",
                        "model_reasoning_effort_source": "override",
                        "model_config_durability": "thread_fork_only",
                    }
                ),
            ),
            CommandStep(
                ["instance", "status", "act-pm-demo", "--json"],
                command_json(active_status("act-pm-demo", "thread-main", "idle")),
            ),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api(
        "POST",
        "/api/instances/act-pm-demo/side",
        b'{"text":"Start side","model":"gpt-5.4","effort":"high"}',
    )

    self.assertEqual(status, 200)
    self.assertEqual(payload["side_thread_id"], "thread-side-1")
    self.assertEqual(payload["model"], "gpt-5.4")
    self.assertEqual(payload["model_reasoning_effort"], "high")
    self.assertEqual(payload["model_config_durability"], "thread_fork_only")
```

- [ ] **Step 2: Add Web rejection test for send-time model changes**

Add this test:

```python
def test_side_route_rejects_model_or_effort_with_existing_side_thread_id(self) -> None:
    runner, base_url = self._start_server()
    status, payload = self._request_json(
        base_url,
        method="POST",
        path="/api/instances/act-pm-demo/side",
        payload={
            "side_thread_id": "thread-side-1",
            "text": "Follow up",
            "model": "gpt-5.4",
            "effort": "high",
        },
    )
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
    self.assertIn("only applies when starting a new side thread", payload["error"]["message"])
    self.assertEqual(runner.calls, [])
```

- [ ] **Step 3: Run Web tests red**

Run:

```bash
python -m unittest -q tests.test_web_management
```

Expected before implementation: missing pass-through args or missing validation failure.

- [ ] **Step 4: Parse and validate Web DTO fields**

In `tools/launcher/web_management.py::_side()`:

```python
model = payload.get("model")
if model is not None and (not isinstance(model, str) or not model.strip()):
    raise HttpError(status=400, code="INVALID_REQUEST", message="model must not be empty.")
effort = payload.get("effort")
if effort is not None and (not isinstance(effort, str) or not effort.strip()):
    raise HttpError(status=400, code="INVALID_REQUEST", message="effort must not be empty.")
if side_thread_id is not None and (model is not None or effort is not None):
    raise HttpError(
        status=400,
        code="INVALID_REQUEST",
        message="model and effort only applies when starting a new side thread.",
    )
```

Pass normalized values to `_side_under_lock()`.

- [ ] **Step 5: Pass Web DTO fields to CLI command only on start**

Update `_side_under_lock()` and `_run_side_command()` signatures to accept `model` and `effort`. Add CLI args only when `side_thread_id is None`:

```python
if side_thread_id is None:
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
```

Do not add these args to send commands.

- [ ] **Step 6: Preserve model response facts**

Update `_side_under_lock()` response projection:

```python
for key in (
    "action",
    "thread_action",
    "parent_thread_id",
    "side_thread_id",
    "turn_id",
    "expected_turn_id",
    "model",
    "model_reasoning_effort",
    "model_source",
    "model_reasoning_effort_source",
    "model_config_durability",
):
    value = parsed.get(key)
    if isinstance(value, str):
        payload[key] = value
```

- [ ] **Step 7: Run Web tests green**

Run:

```bash
python -m unittest -q tests.test_web_management
```

Expected: Web management tests pass.

## Task 5: Preserve Application Runtime Boundaries

**Files:**

- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tools/launcher/task_sys_runtime.py` only if an explicit model source already exists in context
- Modify: `tools/launcher/daemon_core.py` only if an explicit daemon side model source already exists in context

- [ ] **Step 1: Keep Task Sys default inheritance explicit in tests**

Update existing Task Sys lifecycle delegation assertions to confirm no hidden side model policy is introduced:

```python
self.assertNotIn("model", call)
self.assertNotIn("model_reasoning_effort", call)
```

If the implementation passes explicit keyword defaults, assert them as `None` instead:

```python
self.assertIsNone(call["model"])
self.assertIsNone(call["model_reasoning_effort"])
```

Use the version that matches the final call shape.

- [ ] **Step 2: Keep daemon side triage default inheritance explicit in tests**

In `tests/test_daemon_service_contract.py::test_submit_side_triage_prompt_starts_or_reuses_side_and_records_runtime_facts`, assert the captured lifecycle call does not choose a model:

```python
self.assertNotIn("model", calls[0])
self.assertNotIn("model_reasoning_effort", calls[0])
```

If `find_or_start_side_thread()` uses explicit keyword defaults, assert both are `None`.

- [ ] **Step 3: Do not add policy code to Task Sys or daemon without a real source**

Leave current calls as inheritance defaults:

```python
started = side_thread_lifecycle.start_side_thread(
    socket_path=_socket_path(context),
    instance_json=_instance_json(context),
    actor_id=_context_actor_id(context),
    parent_thread_id=parent_thread_id,
    text=frame_text,
    purpose="task_sys.side_frame",
    workspace_dir=_workspace_dir(context),
    shared_project_workspace_dir=_project_workspace_dir(context),
    permissions=_permissions(context),
    task_id=task_id,
)
```

```python
result = side_thread_lifecycle.find_or_start_side_thread(
    socket_path=self.context.socket_path,
    instance_json=self.context.instance_json,
    actor_id=self.context.actor_id,
    parent_thread_id=self.context.main_thread_id,
    text=text,
    purpose="daemon.side_triage",
    workspace_dir=self.context.workspace_dir,
    shared_project_workspace_dir=self.context.project_workspace_dir,
    permissions=self.context.permissions,
)
```

- [ ] **Step 4: Run application boundary tests**

Run:

```bash
python -m unittest -q tests.test_task_sys_runtime_executor tests.test_daemon_service_contract
```

Expected: both suites pass and continue proving application flows delegate to the lifecycle owner.

## Task 6: Strengthen Residue And No-Persistence Proofs

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Extend side lifecycle residue scan to shell helper surfaces**

Update `test_side_thread_lifecycle_boundary_has_no_direct_call_residue()` so live shell helpers cannot expose direct registry lifecycle operations outside `side_thread_registry.py` and lifecycle tests. Add exact stale shell helper names:

```python
legacy_shell_helpers = (
    "buddyswitch_instance_register_side_thread",
    "buddyswitch_instance_require_side_thread",
    "buddyswitch_instance_unregister_side_thread",
)
for helper in legacy_shell_helpers:
    helper_hits = [
        line
        for line in self._scan_targets(helper, targets)
        if not line.startswith(("docs/memo/",))
    ]
    self.assertEqual(helper_hits, [], msg="\n".join(helper_hits))
```

If `_scan_targets()` does not include docs, omit the `docs/memo/` exception.

- [ ] **Step 2: Add no-persistence scan for side-thread model implementation**

Add a focused scan that fails if BuddySwitch side-thread code uses persistent model mutation APIs:

```python
def test_side_thread_model_override_has_no_persistent_config_write_path(self) -> None:
    targets = ["tools/launcher", "scripts/env", "buddyswitch-codex", "tests"]
    forbidden = (
        "thread/settings/update",
        "config/batchWrite",
        "PersistModelSelection",
        "UpdateModel",
    )
    hits = []
    for token in forbidden:
        hits.extend(self._scan_targets(token, targets))
    allowed_prefixes = (
        "tests/test_repo_consistency.py:",
    )
    live_hits = [line for line in hits if not line.startswith(allowed_prefixes)]
    self.assertEqual(live_hits, [], msg="\n".join(live_hits))
```

- [ ] **Step 3: Run repo consistency tests red if residue remains**

Run:

```bash
python -m unittest -q tests.test_repo_consistency
```

Expected before deleting shell helpers: failure listing `buddyswitch_instance_register_side_thread`, `buddyswitch_instance_require_side_thread`, or `buddyswitch_instance_unregister_side_thread`.

- [ ] **Step 4: Delete residue and rerun consistency tests**

After removing shell helper residue in Task 3, run:

```bash
python -m unittest -q tests.test_repo_consistency
```

Expected: repo consistency tests pass.

## Task 7: Full Focused Verification

**Files:**

- No additional code files.

- [ ] **Step 1: Run focused behavior suites**

Run:

```bash
python -m unittest -q \
  tests.test_app_server_client \
  tests.test_side_thread_lifecycle \
  tests.test_web_management \
  tests.test_buddyswitch_launcher \
  tests.test_task_sys_runtime_executor \
  tests.test_daemon_service_contract \
  tests.test_repo_consistency
```

Expected:

```text
OK
```

- [ ] **Step 2: Run exact live-surface scans**

Run:

```bash
rg -n "buddyswitch_instance_(register|require|unregister)_side_thread" tools/launcher scripts/env buddyswitch-codex tests
rg -n "thread/settings/update|config/batchWrite|PersistModelSelection|UpdateModel" tools/launcher scripts/env buddyswitch-codex tests
```

Expected:

```text
no matches, except the explicit forbidden-token assertions inside tests/test_repo_consistency.py
```

- [ ] **Step 3: Inspect a captured launcher RPC row**

Use the passing launcher test capture or a temporary manual launcher run. Confirm the side start with overrides emits exactly:

```json
{
  "rpc_method": "thread/fork",
  "params": {
    "model": "gpt-5.4",
    "config": {
      "model_reasoning_effort": "high"
    }
  }
}
```

Also confirm no captured row has:

```text
thread/settings/update
config/batchWrite
```

- [ ] **Step 4: Confirm inherited-default RPC shape**

Use the focused app-server client test or a temporary launcher run without `--model` and without `--effort`. Confirm `thread/fork` params omit:

```text
model
config
modelProvider
```

This is the proof that `None` means parent inheritance, not JSON null or a BuddySwitch default.

## Completion Checklist

The work is complete only when all of these are true:

- New side-thread creation accepts `model` and `effort` from CLI and Web.
- `app_server.thread_fork()` sends `model` and `config.model_reasoning_effort` only when non-`None`.
- No code path passes JSON null for inherited model or effort.
- Existing side-thread send rejects `model` and `effort` before RPC mutation.
- `side_thread_registry` persists no model or effort fields.
- Task Sys and daemon side triage keep inheriting parent settings unless a future explicit policy source is added.
- `thread/settings/update`, `config/batchWrite`, `PersistModelSelection`, and `UpdateModel` are absent from BuddySwitch side-thread implementation paths.
- Direct shell registry lifecycle helpers are removed from `env.sh`.
- Focused behavior tests pass.
- Residue scans pass.

## Implementation Order Summary

1. Pin `thread_fork` request shape with failing tests.
2. Add primitive request serialization.
3. Pin lifecycle owner behavior and no registry persistence.
4. Add lifecycle parameters and CLI start flags.
5. Add CLI/Web projections and send-time rejection.
6. Preserve Task Sys and daemon default inheritance.
7. Strengthen residue scans and remove shell registry helpers.
8. Run focused verification and inspect captured RPC payloads.
