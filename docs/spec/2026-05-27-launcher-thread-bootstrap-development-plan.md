# Launcher Thread Bootstrap Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move empty-rollout bootstrap into the BuddySwitch launcher so start/clear create daemon-bindable main threads without any Web init prompt.

**Architecture:** Keep app-server service mode as the main control path from `docs/memo/2026-05-23-cowork-forward-stages.md`. Launcher owns main-thread bootstrap by calling Codex `thread/inject_items` immediately after creating a new main thread and before daemon binding. Web API delegates lifecycle to launcher and no longer knows about initialization prompts.

**Tech Stack:** Bash launcher, Python standard library, existing `tools/launcher/app_server.py` WebSocket JSON-RPC client, existing fake Codex server, pytest/unittest, Node built-in `assert`.

---

## Current Bottleneck

Daemon start now correctly uses `thread/resume` to prove that the daemon connection is bound to the instance main thread. That fails for a brand-new empty thread because Codex creates the in-memory thread first and materializes rollout only after a persisted item exists.

The old Web workaround sent a fixed init prompt after Web create/clear. That cannot help launcher CLI start/clear and it cannot help daemon ready because Web init runs only after launcher start/clear succeeds. The forward fix is to make launcher start/clear materialize the main thread natively.

## Design Decisions

1. Use `thread/inject_items` for launcher bootstrap.
   - It is a Codex app-server API.
   - It persists raw Responses API items to rollout.
   - It does not start a user turn or call the model.

2. Inject exactly one low-semantic assistant marker:

```json
{
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "output_text",
      "text": "[BuddySwitch internal bootstrap marker]"
    }
  ]
}
```

3. Do not use Web init prompt anywhere.
   - Remove `INITIALIZE_THREAD_PROMPT`.
   - Remove Web initialize route.
   - Remove Retry Initialize UI.
   - Create/clear Web routes call launcher and then refresh status.

4. Keep daemon behavior unchanged.
   - Daemon still uses `thread/resume` for binding.
   - Daemon still sends STOP Task TUI through real main-thread `turn/start`.
   - Daemon does not poll `instance.json` and does not decide task state.

5. Keep clear failure semantics.
   - Once clear creates a new thread id, preserve it.
   - If bootstrap or daemon start fails after that, stop active runtime, mark inactive, and do not roll back to the old thread.

6. Do not retro-repair legacy empty stopped threads.
   - `instance resume` remains a real `thread/resume`.
   - If the stored rollout is missing, Codex error is reported.

## Files To Modify

- `tools/launcher/app_server.py`
  - Add bootstrap marker constant.
  - Add `thread_bootstrap_rollout(...)`.
  - Add CLI subcommand for main-thread bootstrap.

- `tools/launcher/app_server.sh`
  - Add `buddyswitch_app_server_thread_bootstrap <thread-id>`.

- `buddyswitch-codex`
  - Call bootstrap after `thread/start` in `start_locked_bootstrap`.
  - Call bootstrap after clear creates the new thread id and before replacement daemon start.
  - Keep resume unchanged.

- `tools/launcher/web_management.py`
  - Remove fixed init prompt constant.
  - Remove init wait settings and helper.
  - Remove initialize route.
  - Make create/clear return refreshed status after launcher command success.

- `tools/launcher/assets/web-management/index.html`
  - Remove Retry Initialize button.

- `tools/launcher/assets/web-management/app.js`
  - Remove `canInitialize`, element wiring, and `/initialize` mutation.

- `tests/helpers/fake_codex.py`
  - Model empty rollout until `thread/inject_items` or `turn/start`.
  - Preserve existing explicit error injection hooks.

- `tests/test_app_server_client.py`
  - Add bootstrap helper tests.

- `tests/test_buddyswitch_launcher.py`
  - Add launcher start/clear bootstrap tests and failure tests.
  - Update daemon lifecycle tests to expect bootstrap before daemon resume.

- `tests/test_web_management.py`
  - Replace Web init tests with lifecycle-delegation tests.
  - Add removed initialize-route test.

- `tests/web_management_ui_state.test.js`
  - Remove initialize action expectations.

## Implementation Tasks

### Task 1: Add App-server Bootstrap Tests

**Files:**
- Modify: `tests/test_app_server_client.py`

- [ ] **Step 1: Add marker-shape test**

Add this test to `AppServerClientTests`:

```python
def test_thread_bootstrap_rollout_injects_minimal_marker(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        socket_path = self._socket_path(Path(temp_root))
        server = FakeUnixWebSocketServer(socket_path)
        server.start()
        self.addCleanup(server.close)

        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def run_bootstrap() -> None:
            try:
                results.append(APP_SERVER.thread_bootstrap_rollout(socket_path, "thread-1"))
            except BaseException as exc:
                errors.append(exc)

        bootstrap_thread = threading.Thread(target=run_bootstrap, daemon=True)
        bootstrap_thread.start()

        init = server.next_message()
        self.assertEqual(init["method"], "initialize")
        server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
        self.assertEqual(server.next_message()["method"], "initialized")

        request = server.next_message()
        self.assertEqual(request["method"], "thread/inject_items")
        params = request["params"]
        assert isinstance(params, dict)
        self.assertEqual(params["threadId"], "thread-1")
        self.assertEqual(
            params["items"],
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "[BuddySwitch internal bootstrap marker]",
                        }
                    ],
                }
            ],
        )
        server.send_response(request["id"], {})
        bootstrap_thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(results, [{"ok": True, "thread_id": "thread-1"}])
```

- [ ] **Step 2: Add error propagation test**

```python
def test_thread_bootstrap_rollout_propagates_inject_items_error(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        socket_path = self._socket_path(Path(temp_root))
        server = FakeUnixWebSocketServer(socket_path)
        server.start()
        self.addCleanup(server.close)

        errors: list[BaseException] = []

        def run_bootstrap() -> None:
            try:
                APP_SERVER.thread_bootstrap_rollout(socket_path, "thread-1")
            except BaseException as exc:
                errors.append(exc)

        bootstrap_thread = threading.Thread(target=run_bootstrap, daemon=True)
        bootstrap_thread.start()

        init = server.next_message()
        self.assertEqual(init["method"], "initialize")
        server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
        self.assertEqual(server.next_message()["method"], "initialized")

        request = server.next_message()
        self.assertEqual(request["method"], "thread/inject_items")
        server.send_error(request["id"], code=-32000, message="inject failed")
        bootstrap_thread.join(timeout=2)

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], APP_SERVER.AppServerRequestError)
        self.assertIn("thread/inject_items failed", str(errors[0]))
```

- [ ] **Step 3: Run red test**

```bash
python3 -m pytest tests/test_app_server_client.py::AppServerClientTests::test_thread_bootstrap_rollout_injects_minimal_marker tests/test_app_server_client.py::AppServerClientTests::test_thread_bootstrap_rollout_propagates_inject_items_error -q
```

Expected: FAIL because `thread_bootstrap_rollout` does not exist.

### Task 2: Implement App-server Bootstrap Helper

**Files:**
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`

- [ ] **Step 1: Add constants and helper**

Add near the other app-server constants/functions:

```python
BOOTSTRAP_MARKER_TEXT = "[BuddySwitch internal bootstrap marker]"


def thread_bootstrap_marker_item() -> dict[str, object]:
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": BOOTSTRAP_MARKER_TEXT}],
    }


def thread_bootstrap_rollout(socket_path: Path, thread_id: str) -> dict[str, Any]:
    if not thread_id:
        raise AppServerProtocolError("thread bootstrap requires a thread id")
    thread_inject_items(socket_path, thread_id, [thread_bootstrap_marker_item()])
    return {"ok": True, "thread_id": thread_id}
```

- [ ] **Step 2: Add CLI command**

Add command handler:

```python
def _command_thread_bootstrap(args: argparse.Namespace) -> int:
    payload = thread_bootstrap_rollout(Path(args.socket), args.thread_id)
    print(json.dumps(payload, ensure_ascii=True))
    return 0
```

Add parser next to `thread-resume`/`thread-read`:

```python
thread_bootstrap_parser = subparsers.add_parser("thread-bootstrap")
thread_bootstrap_parser.add_argument("--socket", required=True)
thread_bootstrap_parser.add_argument("--thread-id", required=True)
thread_bootstrap_parser.set_defaults(func=_command_thread_bootstrap)
```

- [ ] **Step 3: Add shell wrapper**

Add to `tools/launcher/app_server.sh` after `buddyswitch_app_server_thread_resume()`:

```bash
buddyswitch_app_server_thread_bootstrap() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-bootstrap \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}
```

- [ ] **Step 4: Run helper tests**

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected: PASS.

### Task 3: Make Fake Codex Model Empty Rollouts

**Files:**
- Modify: `tests/helpers/fake_codex.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add fake behavior tests**

Add focused tests near existing fake Codex/launcher lifecycle tests:

```python
def test_fake_codex_inject_items_materializes_target_thread(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)
        state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
        main_thread = state_payload["threads"][ctx["instance_payload"]["thread_id"]]
        self.assertTrue(main_thread["rollout_materialized"])
        self.assertEqual(main_thread["injected_items"][0]["role"], "assistant")
```

Add a legacy resume failure test that creates an inactive instance with an unmaterialized thread using existing helpers or a minimal instance record fixture:

```python
def test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)
        stop_result = subprocess.run(
            [str(LAUNCHER), "instance", "stop", ctx["instance_id"], "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
        state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
        state_payload["threads"][ctx["instance_payload"]["thread_id"]]["rollout_materialized"] = False
        Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", ctx["instance_id"], "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(resume_result.returncode, 0)
        self.assertIn("no rollout found", resume_result.stderr)
```

- [ ] **Step 2: Run red tests**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_inject_items_materializes_target_thread tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread -q
```

Expected: at least one failure until fake Codex models materialization and launcher bootstrap exists.

- [ ] **Step 3: Update fake thread state**

In `tests/helpers/fake_codex.py`, ensure each thread state has:

```python
"rollout_materialized": False
```

For `thread/start`:

```python
thread = _thread_state(state, thread_id)
thread["status"] = {"type": "idle"}
thread["turns"] = []
thread["injected_items"] = []
thread["rollout_materialized"] = False
```

For `thread/inject_items` mutation:

```python
thread["injected_items"] = [*thread.get("injected_items", []), *items]
thread["rollout_materialized"] = True
```

For `turn/start` mutation:

```python
thread["rollout_materialized"] = True
```

For `thread/resume`, before returning the default success response:

```python
thread = _thread_state(state, thread_id)
if thread.get("rollout_materialized") is False:
    save_server_state(state)
    return rpc_error_response(request_id, -32600, f"no rollout found for thread id {thread_id}")
```

Keep existing `thread_resume_error_on_count` and `errors["thread/resume"]` behavior before default success so current failure tests remain deterministic.

- [ ] **Step 4: Run focused launcher tests**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_inject_items_materializes_target_thread tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread -q
```

Expected after Task 5 implementation: PASS. During this task alone, start may still fail until launcher bootstrap is added.

### Task 4: Add Launcher Start/Clear Bootstrap Tests

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add start call-order test**

```python
def test_start_bootstraps_main_thread_rollout_before_daemon_resume(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)

        calls = self._read_json_lines(Path(str(ctx["calls_path"])))
        rpc_rows = [row for row in calls if row.get("argv", [])[:1] == ["json-rpc"]]
        thread_id = ctx["instance_payload"]["thread_id"]
        relevant = [
            row
            for row in rpc_rows
            if row.get("rpc_method") in {"thread/start", "thread/inject_items", "thread/resume"}
        ]
        start_index = next(i for i, row in enumerate(relevant) if row["rpc_method"] == "thread/start")
        inject_index = next(i for i, row in enumerate(relevant) if row["rpc_method"] == "thread/inject_items")
        daemon_resume_index = next(
            i
            for i, row in enumerate(relevant)
            if row["rpc_method"] == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
        )

        self.assertLess(start_index, inject_index)
        self.assertLess(inject_index, daemon_resume_index)
        self.assertEqual(relevant[inject_index]["params"]["threadId"], thread_id)
        self.assertEqual(relevant[daemon_resume_index]["params"]["threadId"], thread_id)
```

- [ ] **Step 2: Add marker and no-turn bootstrap test**

```python
def test_start_bootstrap_uses_inject_items_not_turn_start(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)

        rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
        bootstrap = next(row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items")
        self.assertEqual(bootstrap["params"]["threadId"], ctx["instance_payload"]["thread_id"])
        self.assertEqual(
            bootstrap["params"]["items"],
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "[BuddySwitch internal bootstrap marker]",
                        }
                    ],
                }
            ],
        )
        self.assertNotIn(
            "Initialize this BuddySwitch thread",
            json.dumps(self._read_json_lines(Path(str(ctx["calls_path"])))),
        )
        launcher_turn_starts = [
            row
            for row in rpc_rows
            if row.get("rpc_method") == "turn/start" and row.get("client_name") == "buddyswitch_launcher"
        ]
        self.assertEqual(launcher_turn_starts, [])
```

- [ ] **Step 3: Add start bootstrap failure test**

```python
def test_start_bootstrap_failure_fails_closed_without_ready_daemon(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(
            Path(temp_root),
            Path(source_home),
            buddy="pm",
            state_payload={
                "errors": {
                    "thread/inject_items": {
                        "code": -32000,
                        "message": "inject failed",
                    }
                }
            },
        )
        completed = ctx["completed"]
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("thread/inject_items failed", completed.stderr)

        instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["status"], "inactive")
        self.assertIsNone(instance_payload["app_server_pid"])
        self.assertIsNone(instance_payload["app_server_socket"])
        self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())
```

- [ ] **Step 4: Add clear bootstrap tests**

```python
def test_clear_bootstraps_new_thread_before_daemon_resume(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(
            Path(temp_root),
            Path(source_home),
            state_payload={"clear_thread_id": "thread-cleared"},
        )
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)
        Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

        clear_result = subprocess.run(
            [str(LAUNCHER), "instance", "clear", ctx["instance_id"], "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)

        calls = self._read_rpc_rows(Path(str(ctx["calls_path"])))
        start = next(row for row in calls if row.get("rpc_method") == "thread/start")
        inject = next(row for row in calls if row.get("rpc_method") == "thread/inject_items")
        daemon_resume = next(
            row
            for row in calls
            if row.get("rpc_method") == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
        )
        self.assertEqual(start["params"]["sessionStartSource"], "clear")
        self.assertEqual(inject["params"]["threadId"], "thread-cleared")
        self.assertEqual(daemon_resume["params"]["threadId"], "thread-cleared")
```

```python
def test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(
            Path(temp_root),
            Path(source_home),
            state_payload={"clear_thread_id": "thread-cleared"},
        )
        self.assertEqual(ctx["completed"].returncode, 0, msg=ctx["completed"].stderr)
        state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
        state_payload["errors"] = {
            "thread/inject_items": {
                "code": -32000,
                "message": "inject failed",
            }
        }
        Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        clear_result = subprocess.run(
            [str(LAUNCHER), "instance", "clear", ctx["instance_id"], "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(clear_result.returncode, 0)
        instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["thread_id"], "thread-cleared")
        self.assertEqual(instance_payload["status"], "inactive")
        self.assertIsNone(instance_payload["app_server_pid"])
        self.assertIsNone(instance_payload["app_server_socket"])
        self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())
```

- [ ] **Step 5: Run red launcher tests**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstraps_main_thread_rollout_before_daemon_resume tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstrap_uses_inject_items_not_turn_start tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstrap_failure_fails_closed_without_ready_daemon tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_clear_bootstraps_new_thread_before_daemon_resume tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime -q
```

Expected: FAIL before launcher bootstrap is wired.

### Task 5: Implement Launcher Bootstrap In Start And Clear

**Files:**
- Modify: `buddyswitch-codex`

- [ ] **Step 1: Add start bootstrap call**

In `start_locked_bootstrap`, after parsing `thread_id` and before `buddyswitch_instance_set_app_server`, add:

```bash
  if ! buddyswitch_app_server_thread_bootstrap "${thread_id}" >/dev/null; then
    echo "Thread bootstrap failed for ${thread_id}." >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_instance_stop "${requested_instance_id}" || true
    buddyswitch_instance_clear_app_server "${requested_instance_id}" "inactive"
    return 1
  fi
```

- [ ] **Step 2: Add clear bootstrap call**

In `instance_clear`, after `buddyswitch_instance_set_thread_id "${instance_id}" "${new_thread_id}"` and before `buddyswitch_daemon_start`, add:

```bash
  if ! buddyswitch_app_server_thread_bootstrap "${new_thread_id}" >/dev/null; then
    echo "Thread bootstrap failed for ${new_thread_id}." >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_instance_stop "${instance_id}" || true
    buddyswitch_instance_clear_app_server "${instance_id}" "inactive"
    return 1
  fi
```

This preserves the new clear thread id because `buddyswitch_instance_clear_app_server` clears app-server fields but does not clear `thread_id`.

- [ ] **Step 3: Keep resume unchanged**

Do not add bootstrap to `instance_resume_locked`.

- [ ] **Step 4: Run launcher focused tests**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstraps_main_thread_rollout_before_daemon_resume tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstrap_uses_inject_items_not_turn_start tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_bootstrap_failure_fails_closed_without_ready_daemon tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_clear_bootstraps_new_thread_before_daemon_resume tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime -q
```

Expected: PASS.

- [ ] **Step 5: Run existing daemon/launcher lifecycle tests**

```bash
python3 -m pytest tests/test_stop_task_daemon.py tests/test_buddyswitch_launcher.py -q
```

Expected: PASS after updating any expected call ordering to include `thread/inject_items`.

### Task 6: Remove Web Init API Tests And Add Delegation Tests

**Files:**
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Replace create init test**

Replace `test_create_instance_initializes_thread_before_returning` with:

```python
def test_create_instance_delegates_to_launcher_start_without_initialize_input(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "buddies", "--json"],
                command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]}),
            ),
            CommandStep(
                ["instance", "start", "--buddy", "pm", "--json"],
                command_json({"instance_id": "inst-pm-demo"}),
            ),
            CommandStep(
                ["instance", "status", "inst-pm-demo", "--json"],
                command_json(active_status("inst-pm-demo", "thread-1", "idle")),
            ),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["instance_id"], "inst-pm-demo")
    self.assertEqual(payload["instance"]["thread"]["thread_id"], "thread-1")
    self.assertEqual(len(runner.calls), 3)
    self.assertNotIn("Initialize this BuddySwitch thread", json.dumps(runner.calls))
```

- [ ] **Step 2: Replace create init failure tests**

Remove initialization failure/timeout tests. Add:

```python
def test_create_instance_returns_launcher_start_error_without_initialize_retry(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "buddies", "--json"],
                command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]}),
            ),
            CommandStep(
                ["instance", "start", "--buddy", "pm", "--json"],
                command_error(returncode=1, stderr="Thread bootstrap failed for thread-1."),
            ),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
        service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

    self.assertEqual(raised.exception.status, 502)
    self.assertEqual(raised.exception.code, "COMMAND_FAILED")
    self.assertIn("Thread bootstrap failed", raised.exception.message)
    self.assertEqual(len(runner.calls), 2)
```

- [ ] **Step 3: Replace clear init test**

```python
def test_clear_route_delegates_to_launcher_clear_without_initialize_input(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "clear", "inst-pm-demo", "--json"],
                command_json(
                    {
                        "instance_id": "inst-pm-demo",
                        "previous_thread_id": "thread-old",
                        "thread_id": "thread-new",
                    }
                ),
            ),
            CommandStep(
                ["instance", "status", "inst-pm-demo", "--json"],
                command_json(active_status("inst-pm-demo", "thread-new", "idle")),
            ),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/clear", b"")

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["previous_thread_id"], "thread-old")
    self.assertEqual(payload["thread_id"], "thread-new")
    self.assertEqual(payload["instance"]["thread"]["thread_id"], "thread-new")
    self.assertEqual(len(runner.calls), 2)
    self.assertNotIn("Initialize this BuddySwitch thread", json.dumps(runner.calls))
```

- [ ] **Step 4: Replace initialize route test**

Replace `test_initialize_route_sends_fixed_prompt_and_waits` with:

```python
def test_initialize_route_is_removed(self) -> None:
    runner = OrderedRunner([])
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
        service.handle_api("POST", "/api/instances/inst-pm-demo/initialize", b"")

    self.assertEqual(raised.exception.status, 404)
    self.assertEqual(raised.exception.code, "NOT_FOUND")
    self.assertEqual(runner.calls, [])
```

- [ ] **Step 5: Update prompt absence test**

Keep the normal input test, but assert by literal string instead of the removed constant:

```python
self.assertNotIn("Initialize this BuddySwitch thread", json.dumps(runner.calls))
self.assertNotIn("[BuddySwitch internal bootstrap marker]", json.dumps(runner.calls))
```

- [ ] **Step 6: Run red Web tests**

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: FAIL until Web implementation removes init behavior.

### Task 7: Remove Web Init Implementation

**Files:**
- Modify: `tools/launcher/web_management.py`

- [ ] **Step 1: Remove constants and constructor fields**

Delete:

```python
INITIALIZE_THREAD_PROMPT = "Initialize this BuddySwitch thread. Do not perform any task or use tools. Reply exactly: ready"
ACTIVE_THREAD_STATUSES = {"active", "in_progress"}
DEFAULT_INIT_WAIT_TIMEOUT_SECONDS = 120.0
DEFAULT_INIT_WAIT_POLL_SECONDS = 0.25
```

Remove `init_wait_timeout_seconds` and `init_wait_poll_seconds` from `WebManagementService.__init__`.

- [ ] **Step 2: Remove initialize route parsing**

Delete handling for:

```python
if method == "POST" and action == "initialize":
    return 200, self._initialize(instance_id)
```

Delete `/initialize` from `_parse_instance_action_path`.

- [ ] **Step 3: Replace create implementation**

Use:

```python
def _create_instance_under_lock(self, buddy: str) -> dict[str, Any]:
    result = self._run_command(["instance", "start", "--buddy", buddy, "--json"], timeout_seconds=120)
    payload = load_command_json_object(
        result.stdout,
        message=f"Invalid JSON from instance start for buddy {buddy}.",
    )
    instance_id = payload.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        raise HttpError(status=502, code="COMMAND_FAILED", message=f"Invalid start payload for buddy {buddy}.")
    return {"ok": True, "instance_id": instance_id, "instance": self._get_instance_status(instance_id)}
```

- [ ] **Step 4: Replace clear implementation**

Use:

```python
def _clear_under_lock(self, instance_id: str) -> dict[str, Any]:
    result = self._run_command(["instance", "clear", instance_id, "--json"], timeout_seconds=60)
    cleared = load_command_json_object(
        result.stdout,
        message=f"Invalid JSON from instance clear for {instance_id}.",
    )
    payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
    previous_thread_id = cleared.get("previous_thread_id")
    thread_id = cleared.get("thread_id")
    if isinstance(previous_thread_id, str):
        payload["previous_thread_id"] = previous_thread_id
    if isinstance(thread_id, str):
        payload["thread_id"] = thread_id
    return payload
```

- [ ] **Step 5: Delete init helpers**

Delete:

```python
def _initialize(...)
def _run_initialize_under_lock(...)
def _wait_for_instance_idle(...)
```

Keep `_run_input_command(...)` for normal user input.

- [ ] **Step 6: Run Web tests**

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: PASS.

### Task 8: Remove Retry Initialize UI

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`

- [ ] **Step 1: Remove UI test expectations**

In `tests/web_management_ui_state.test.js`, remove `canInitialize` from every expected object.

Rename tests:

- `active healthy instance allows send, stop, clear, and initialize retry, but not delete`
  to `active healthy instance allows send, stop, and clear, but not delete`.
- `active idle instance allows clear and initialize retry even without draft text`
  to `active idle instance allows clear even without draft text`.
- `active in-progress instance disables clear and initialize while allowing interrupt`
  to `active in-progress instance disables clear while allowing interrupt`.

- [ ] **Step 2: Remove app state and DOM wiring**

In `app.js`:

Delete `canInitialize` from `computeInstanceActionState`.

Delete:

```javascript
elements.initializeButton.disabled = !actionState.canInitialize;
```

Delete:

```javascript
initializeButton: document.getElementById('initialize-button'),
```

Delete the initialize click listener:

```javascript
elements.initializeButton.addEventListener('click', function () {
  runMutation(state, elements, 'initialize', function () {
    return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/initialize', {
      method: 'POST',
    });
  });
});
```

- [ ] **Step 3: Remove button markup**

In `index.html`, delete:

```html
<button id="initialize-button" type="button">Retry Initialize</button>
```

- [ ] **Step 4: Run UI tests**

```bash
node tests/web_management_ui_state.test.js
```

Expected: PASS.

### Task 9: Update Existing Lifecycle Tests For Bootstrap

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_stop_task_daemon.py` only if a focused failure proves an expected call sequence needs the new bootstrap RPC.

- [ ] **Step 1: Update call-order assertions that assumed no bootstrap RPC**

Existing tests that read `thread/start` or `thread/resume` calls should allow `thread/inject_items` between start/clear and daemon resume.

Do not weaken assertions about daemon readiness, main thread id, STOP prompt shape, or input TUI behavior.

- [ ] **Step 2: Ensure daemon loop tests still use real nested Codex schema**

No code change should be needed. If tests fail, fix only the test expectation affected by the new launcher bootstrap call.

- [ ] **Step 3: Run focused suites**

```bash
python3 -m pytest tests/test_stop_task_daemon.py tests/test_buddyswitch_launcher.py -q
```

Expected: PASS.

### Task 10: Review Gates And Full Verification

**Files:**
- No planned code edits.

- [ ] **Step 1: Static removal gate**

```bash
rg -n 'INITIALIZE_THREAD_PROMPT|Initialize this BuddySwitch thread|Reply exactly: ready|Retry Initialize|canInitialize|/initialize' tools tests
```

Expected: no matches.

- [ ] **Step 2: Bootstrap gate**

```bash
rg -n 'thread/inject_items|thread-bootstrap|internal bootstrap marker' tools tests
```

Expected: matches only app-server helper, shell wrapper, side-conversation existing helper use, fake Codex, and tests.

- [ ] **Step 3: Web input gate**

```bash
rg -n 'turn/start|instance input' tools/launcher/web_management.py tests/test_web_management.py
```

Expected: only normal user input tests/path remain; no lifecycle init behavior.

- [ ] **Step 4: Focused tests**

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
```

Expected: PASS.

- [ ] **Step 5: Full test suite**

```bash
python3 -m pytest tests -q
```

Expected: PASS.

## Final Review Checklist

- [ ] `instance start` bootstraps rollout with `thread/inject_items` before daemon `thread/resume`.
- [ ] `instance clear` bootstraps the new thread before daemon `thread/resume`.
- [ ] bootstrap marker is a minimal assistant `output_text` item.
- [ ] no lifecycle path uses fixed Web init prompt.
- [ ] Web create/clear only delegate to launcher and refresh status.
- [ ] Web initialize route and Retry Initialize UI are gone.
- [ ] normal Web input remains unchanged.
- [ ] daemon remains observer + prompt sender.
- [ ] STOP Task TUI still uses real main-thread `turn/start`.
- [ ] daemon-origin turn ids still prevent loops.
- [ ] resume does not bootstrap legacy empty stopped threads.
- [ ] no retry loop, gate, fallback, side workaround, daemon polling, direct JSONL/sqlite write, or old-thread rollback was introduced.
