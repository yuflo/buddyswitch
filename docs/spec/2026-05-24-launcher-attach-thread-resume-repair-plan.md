# Launcher Attach Thread Resume Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `buddyswitch-codex instance attach <instance-id>` attach the TUI to the exact launcher-owned app-server thread, including a running Web-started turn; fresh empty thread attach must be verified against the Codex `thread/resume` contract before claiming fixed.

**Architecture:** Keep one lifecycle truth: Browser UI -> Web API -> launcher CLI -> app-server JSON-RPC -> Codex app-server thread lifecycle. The launcher should preflight the target thread through `thread/resume` on the existing app-server, then launch the human TUI with `codex resume --remote unix://<socket> <thread_id>` so the TUI is pinned to the instance record's `thread_id`. If Codex still rejects loaded-but-unmaterialized empty threads, stop at the Codex boundary instead of adding a BuddySwitch fallback.

**Tech Stack:** Bash launcher, Python app-server JSON-RPC helper over WebSocket/UDS, existing fake Codex app-server test harness, `pytest`, Node UI state tests.

---

## Investigation Summary

### Confirmed Evidence

- Current code at `buddyswitch-codex` launches attach as `codex --remote unix://<socket>`, without `resume` and without `<thread_id>`.
- The live instance investigation showed Web input created a real turn on the instance thread:
  - instance: `inst-pm-21f7d5089d32`
  - thread: `019e5a80-4c59-74c2-b9cc-89175c794e4d`
  - turn: `019e5a80-ac3c-7c41-b076-eec4662baee1`
  - turn status: `completed`
  - duration: `97989ms`
- TUI logs show the TUI was opened while that turn was running, but the TUI did not show the running task. This is consistent with the TUI connecting to the app-server without being routed to the specific thread.
- Existing service-mode specs still state that attach should run `codex resume --remote unix://<socket> <thread_id>`.
- Generated Codex app-server schema confirms `thread/resume` exists and explicitly says:
  - `threadId` is required.
  - running threads are rejoined by `threadId`.
  - thread id is preferred.
  - `excludeTurns` exists for resume without loading full turns.

### Codex Source Confirmation

Source reviewed in `/Users/chen/Dev/codex` confirms the empty-thread case is not solved by a BuddySwitch-only `thread/resume` preflight:

- `codex-rs/cli/src/main.rs` routes `codex resume --remote <addr> <id>` into the TUI with `resume_session_id`.
- `codex-rs/tui/src/lib.rs` resolves that id by calling app-server `thread/read` and then starts the TUI session by calling `AppServerSession::resume_thread`.
- `codex-rs/tui/src/app_server_session.rs` implements `resume_thread` as an app-server `thread/resume` request.
- `codex-rs/app-server/src/request_processors/thread_processor.rs` handles loaded thread resume by calling `read_stored_thread_for_resume(... include_history=true)` before sending the resume response.
- `codex-rs/app-server/tests/suite/v2/thread_resume.rs::thread_resume_rejects_unmaterialized_thread` explicitly verifies current Codex rejects a thread started with `thread/start` before the first user message materializes rollout storage.

Conclusion: BuddySwitch should still pin attach to `codex resume --remote ... <thread_id>` for active/materialized threads, but fresh empty thread attach needs a Codex contract change or a proven current-Codex protocol path. Do not create a dummy turn, do not write JSONL, and do not add a BuddySwitch transcript fallback.

### Challenged Alternatives

- **Web input started the wrong thread:** Rejected. `thread/read --include-turns` showed the Web user message and final answer on the exact `instance.json.thread_id`.
- **Web active status was fake:** Rejected for the reported run. The thread had an active turn during the TUI-open window. There is a separate stale-snapshot UX risk because the Web UI does not poll automatically after `refreshAll`.
- **TUI hid a correctly attached running turn:** Not fully disproved from screen state alone. The stronger evidence is that current attach no longer supplies a thread id, while the intended and documented attach contract requires one.
- **Simply reverting to `codex resume --remote ... <thread_id>` is enough:** Rejected as incomplete. It fixes the selected-thread routing problem for materialized/running threads, but current Codex source and tests show fresh empty threads still fail at app-server `thread/resume` because no rollout exists yet.
- **BuddySwitch should implement its own TUI replay:** Rejected. That would duplicate Codex lifecycle and transcript truth. BuddySwitch should only call Codex app-server and Codex TUI contracts.

### Adjacent Risks Found

- `instance clear` creates a fresh empty thread. It will hit the same attach problem if attach only works for materialized threads.
- `instance compact`, `goal`, and `interrupt` depend on the same active service/thread lookup helper; they should not be changed for this repair except through shared app-server client additions.
- Web interrupt currently enables on `thread.status in {"active", "in_progress"}`. If the active snapshot becomes stale before the user clicks, the server can still reject with "no active in-progress turn"; this is a UX risk, not the attach root cause.
- Current attach tests assert only the spawned argv shape. They do not prove app-server `thread/resume` is called, that empty threads are preflighted, or that a running thread remains the selected TUI target.

## Scope

In scope:

- Add launcher-owned app-server `thread/resume` wrapper.
- Make attach preflight the exact instance thread with app-server `thread/resume`.
- Restore TUI launch to `codex resume --remote unix://<socket> <thread_id>`.
- Add regression tests for active running thread attach and fresh empty thread attach.
- Add a source/protocol gate that proves Codex accepts loaded unmaterialized thread resume before marking fresh empty attach fixed.
- Add focused manual smoke instructions.

Out of scope:

- No Web API for attach.
- No Web API for goal, clear, or compact.
- No polling redesign for the Web UI.
- No direct reads or writes to `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`.
- No local JSONL parser in BuddySwitch.
- No dummy/no-op turn solely to materialize an empty thread.
- No framework, queue, plugin, workflow, auth, or remote service additions.

## Files

- Modify: `tools/launcher/app_server.py`
  - Add `thread_resume(...)` JSON-RPC wrapper and a `thread-resume` CLI subcommand.
- Modify: `tools/launcher/app_server.sh`
  - Add `buddyswitch_app_server_thread_resume`.
- Modify: `buddyswitch-codex`
  - Update `instance_attach` to call app-server `thread/resume` before launching TUI.
  - Restore TUI argv to `resume --remote unix://<socket> <thread_id>`.
- Modify: `tests/helpers/fake_codex.py`
  - Add fake `thread/resume` support and state tracking.
  - Keep local replay behavior out of the fake; assert the launcher preflights and pins the thread instead.
- Modify: `tests/test_app_server_client.py`
  - Cover `thread_resume(...)` request shape.
- Modify: `tests/test_buddyswitch_launcher.py`
  - Replace the current attach argv test with thread-pinned resume tests.
  - Add empty-thread attach regression.
  - Add preflight failure test.

---

### Task 0: Verify Codex Resume Contract Gate

**Files:**

- Read-only: `/Users/chen/Dev/codex/codex-rs/cli/src/main.rs`
- Read-only: `/Users/chen/Dev/codex/codex-rs/tui/src/lib.rs`
- Read-only: `/Users/chen/Dev/codex/codex-rs/tui/src/app_server_session.rs`
- Read-only: `/Users/chen/Dev/codex/codex-rs/app-server/src/request_processors/thread_processor.rs`
- Read-only: `/Users/chen/Dev/codex/codex-rs/app-server/tests/suite/v2/thread_resume.rs`

- [ ] **Step 1: Confirm current Codex behavior from source**

Run:

```bash
rg -n 'finalize_resume_interactive|lookup_session_target_with_app_server|resume_thread\(' /Users/chen/Dev/codex/codex-rs/cli/src/main.rs /Users/chen/Dev/codex/codex-rs/tui/src/lib.rs /Users/chen/Dev/codex/codex-rs/tui/src/app_server_session.rs
rg -n 'resume_running_thread|read_stored_thread_for_resume|thread_resume_rejects_unmaterialized_thread' /Users/chen/Dev/codex/codex-rs/app-server/src/request_processors/thread_processor.rs /Users/chen/Dev/codex/codex-rs/app-server/tests/suite/v2/thread_resume.rs
```

Expected: source shows CLI `resume --remote <id>` resolves through `thread/read`, then calls `thread/resume`; current app-server `thread/resume` reads stored rollout history for loaded threads; the existing Codex test rejects unmaterialized threads.

- [ ] **Step 2: Run the Codex contract test if the Rust test environment is available**

Run:

```bash
cd /Users/chen/Dev/codex/codex-rs
cargo test -p codex-app-server --test suite thread_resume_rejects_unmaterialized_thread -- --exact
```

Expected today: PASS, proving current Codex intentionally rejects `thread/resume` before the first user message materializes rollout storage.

- [ ] **Step 3: Decide the implementation boundary**

If Step 1 or Step 2 still shows the rejection, continue only with the BuddySwitch active/materialized-thread fix and keep fresh empty attach marked blocked by Codex. Do not add a BuddySwitch JSONL writer, dummy turn, fallback parser, or lifecycle clone. Fresh empty attach can move to acceptance only after Codex has a verified contract that resumes loaded unmaterialized threads.

### Task 1: Add Failing App-Server Resume Client Test

**Files:**

- Modify: `tests/test_app_server_client.py`
- Future implementation target: `tools/launcher/app_server.py`

- [ ] **Step 1: Write the failing test**

Add this test near the other request-shape tests in `AppServerClientTests`:

```python
    def test_thread_resume_sends_thread_id_and_runtime_context(self) -> None:
        self.assertTrue(
            hasattr(APP_SERVER, "thread_resume"),
            "APP_SERVER.thread_resume is required for launcher attach preflight",
        )

        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_resume() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_resume(
                            socket_path,
                            "thread-1",
                            workspace_dir=Path("/tmp/bs-workspace"),
                            shared_project_workspace_dir=Path("/tmp/bs-project"),
                            permissions="buddyswitch-runtime",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            resume_thread = threading.Thread(target=run_resume, daemon=True)
            resume_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/resume")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-1")
            self.assertEqual(params["cwd"], "/tmp/bs-workspace")
            self.assertEqual(params["runtimeWorkspaceRoots"], ["/tmp/bs-workspace", "/tmp/bs-project"])
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertEqual(params["excludeTurns"], True)
            self.assertNotIn("path", params)

            server.send_response(
                request["id"],
                {
                    "thread": {"id": "thread-1", "status": {"type": "idle"}},
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
            resume_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["thread"]["id"], "thread-1")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py::AppServerClientTests::test_thread_resume_sends_thread_id_and_runtime_context -q
```

Expected: FAIL at the explicit missing-helper assertion because `APP_SERVER.thread_resume` does not exist. After the helper exists, the same test must continue into the request-shape assertions.

### Task 2: Implement App-Server Thread Resume Wrapper

**Files:**

- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`
- Test: `tests/test_app_server_client.py`

- [ ] **Step 1: Add Python helper**

Add this function next to `thread_start` and `thread_read` in `tools/launcher/app_server.py`:

```python
def thread_resume(
    socket_path: Path,
    thread_id: str,
    *,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "threadId": thread_id,
        "cwd": str(workspace_dir),
        "runtimeWorkspaceRoots": [
            str(workspace_dir),
            str(shared_project_workspace_dir),
        ],
        "permissions": permissions,
        "excludeTurns": True,
    }
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        return client.request("thread/resume", params)
```

- [ ] **Step 2: Add Python CLI command**

Add this command handler:

```python
def _command_thread_resume(args: argparse.Namespace) -> int:
    payload = thread_resume(
        Path(args.socket),
        args.thread_id,
        workspace_dir=Path(args.workspace_dir),
        shared_project_workspace_dir=Path(args.shared_project_workspace_dir),
        permissions=args.permissions,
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0
```

Add this parser block after `thread-start`:

```python
    thread_resume_parser = subparsers.add_parser("thread-resume")
    thread_resume_parser.add_argument("--socket", required=True)
    thread_resume_parser.add_argument("--thread-id", required=True)
    thread_resume_parser.add_argument("--workspace-dir", required=True)
    thread_resume_parser.add_argument("--shared-project-workspace-dir", required=True)
    thread_resume_parser.add_argument("--permissions", required=True)
    thread_resume_parser.set_defaults(func=_command_thread_resume)
```

- [ ] **Step 3: Add shell wrapper**

Add this to `tools/launcher/app_server.sh` near `buddyswitch_app_server_thread_start`:

```bash
buddyswitch_app_server_thread_resume() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-resume \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}" \
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --permissions "buddyswitch-runtime"
}
```

- [ ] **Step 4: Run focused test and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py::AppServerClientTests::test_thread_resume_sends_thread_id_and_runtime_context -q
```

Expected: PASS.

### Task 3: Extend Fake Codex App-Server Resume Behavior

**Files:**

- Modify: `tests/helpers/fake_codex.py`
- Test indirectly: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add default `thread/resume` response**

In `build_default_result`, add before `thread/read`:

```python
    if method == "thread/resume":
        thread = default_thread(state)
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
```

- [ ] **Step 2: Track resume preflight state**

In `maybe_mutate_state`, add after the `thread/start` branch:

```python
    if method == "thread/resume":
        count = state.get("thread_resume_count")
        state["thread_resume_count"] = (count if isinstance(count, int) else 0) + 1
        if isinstance(params, dict):
            state["last_thread_resume_params"] = dict(params)
        return
```

The `thread_resume_response_thread_id` override is only for the attach mismatch regression. Production code must validate the response instead of trusting that the server echoed the requested id.

- [ ] **Step 3: Run existing launcher attach tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'attach_' -q
```

Expected before later tasks: at least the current attach argv test still reflects the old broken contract and will be updated in Task 4.

### Task 4: Add Failing Launcher Attach Regression Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify later: `buddyswitch-codex`

- [ ] **Step 1: Replace current attach argv test with thread-pinned resume expectation**

Rename `test_attach_invokes_remote_tui_without_local_resume_replay` to:

```python
    def test_attach_preflights_thread_resume_then_invokes_remote_resume_tui(self) -> None:
```

Keep the setup, then assert both JSON-RPC and TUI argv:

```python
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], instance_payload["thread_id"])
            self.assertEqual(resume_rpc["params"]["cwd"], instance_payload["workspace_dir"])
            self.assertEqual(resume_rpc["params"]["permissions"], "buddyswitch-runtime")
            self.assertEqual(resume_rpc["params"]["excludeTurns"], True)
            self.assertNotIn("path", resume_rpc["params"])

            self.assertEqual(
                payload["argv"],
                [
                    "resume",
                    "--remote",
                    f"unix://{instance_payload['app_server_socket']}",
                    instance_payload["thread_id"],
                ],
            )
            instance_root = Path(str(ctx["instance_root"]))
            self.assertEqual(payload["cwd"], str((instance_root / "workspace").resolve()))
            self.assertEqual(payload["home"], str(instance_root / "home"))
            self.assertEqual(payload["codex_home"], str(instance_root / "codex-home"))
            self.assertEqual(payload["xdg_config_home"], str(instance_root / "xdg-config"))
            self.assertEqual(payload["instance_json"], str(instance_root / "instance.json"))
```

- [ ] **Step 2: Add active-turn attach test**

Add this test after the renamed attach test:

```python
    def test_attach_to_active_turn_preflights_same_running_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-active",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["instance_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=attach_result.stderr)

            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            payload = json.loads(Path(str(ctx["capture_path"])).read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"][-1], instance_payload["thread_id"])

            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], instance_payload["thread_id"])
```

- [ ] **Step 3: Add resume response mismatch test**

Add this test near attach rejection tests:

```python
    def test_attach_blocks_when_thread_resume_returns_different_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"thread_resume_response_thread_id": "thread-other"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["capture_path"])).unlink(missing_ok=True)
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["instance_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("thread/resume returned unexpected thread id", attach_result.stderr)
            self.assertFalse(Path(str(ctx["capture_path"])).exists(), "TUI must not launch after mismatched preflight")
```

- [ ] **Step 4: Add resume preflight failure test**

Add this test near attach rejection tests:

```python
    def test_attach_blocks_when_thread_resume_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "errors": {
                        "thread/resume": {
                            "code": -32004,
                            "message": "thread not loaded: thread-test",
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["capture_path"])).unlink(missing_ok=True)
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["instance_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("thread/resume failed", attach_result.stderr)
            self.assertFalse(Path(str(ctx["capture_path"])).exists(), "TUI must not launch after failed preflight")
```

- [ ] **Step 5: Run attach tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'attach_' -q
```

Expected: FAIL because `instance_attach` still launches `codex --remote` and does not call `thread/resume`.

### Task 5: Implement Thread-Pinned Attach

**Files:**

- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add preflight in `instance_attach`**

In `instance_attach`, after resolving `socket_path` and before `cd "${BUDDYSWITCH_WORKSPACE_DIR}"`, add:

```bash
  output="$(buddyswitch_app_server_thread_resume "${thread_id}" 2>&1)" || {
    echo "thread/resume failed for ${thread_id}" >&2
    [[ -n "${output}" ]] && echo "${output}" >&2
    return 1
  }
  resumed_thread_id="$(
    python3 -c 'import json, sys; print(json.load(sys.stdin).get("thread", {}).get("id", ""))' <<<"${output}"
  )" || {
    echo "thread/resume returned invalid JSON for ${thread_id}" >&2
    return 1
  }
  if [[ "${resumed_thread_id}" != "${thread_id}" ]]; then
    echo "thread/resume returned unexpected thread id: ${resumed_thread_id}" >&2
    return 1
  fi
```

- [ ] **Step 2: Restore thread-pinned TUI resume**

Replace:

```bash
    buddyswitch_run_codex --remote "unix://${socket_path}"
```

with:

```bash
    buddyswitch_run_codex resume --remote "unix://${socket_path}" "${thread_id}"
```

- [ ] **Step 3: Run focused attach tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'attach_' -q
```

Expected: PASS. The tests must prove:

- `thread/resume` is called before TUI launch.
- `threadId` equals the stored instance thread id.
- `thread/resume` response id equals the stored instance thread id.
- TUI launches from the instance workspace with instance-scoped `HOME`, `CODEX_HOME`, and `XDG_CONFIG_HOME`.
- TUI argv includes `resume --remote unix://<socket> <thread_id>`.
- failed `thread/resume` blocks TUI launch.

### Task 6: Add Clear/Fresh Thread Attach Regression

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `buddyswitch-codex`, `tools/launcher/app_server.py`, `tools/launcher/app_server.sh`

This BuddySwitch fake-Codex regression proves attach uses the current `instance.json.thread_id` after clear. It does not prove real Codex can resume an unmaterialized thread; that proof belongs to Task 0 and manual smoke.

- [ ] **Step 1: Add clear-then-attach test**

Add this test near `test_clear_json_starts_clear_thread_and_updates_instance_record`:

```python
    def test_attach_after_clear_uses_new_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["instance_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)
            self.assertEqual(json.loads(clear_result.stdout)["thread_id"], "thread-cleared")

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["instance_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=attach_result.stderr)

            payload = json.loads(Path(str(ctx["capture_path"])).read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"][-1], "thread-cleared")
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], "thread-cleared")
```

- [ ] **Step 2: Run clear/attach focused tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'clear_json_starts_clear_thread_and_updates_instance_record or attach_after_clear_uses_new_thread_id or attach_' -q
```

Expected: PASS.
If Task 0 still shows current Codex rejects unmaterialized threads, this test only validates BuddySwitch routing and must not be used to claim fresh empty attach is fixed end-to-end.

### Task 7: Focused Regression Gates

**Files:**

- No implementation edits.

- [ ] **Step 1: App-server client regression**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected: PASS.

- [ ] **Step 2: Launcher service-mode regression**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_ or clear_json_starts_clear_thread_and_updates_instance_record' -q
```

Expected: PASS.

- [ ] **Step 3: Web management regression**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
```

Expected: PASS. No Web API contract changes should be required.

### Task 8: Manual Smoke

**Files:**

- No implementation edits.

- [ ] **Step 1: Fresh empty attach smoke**

Run:

```bash
./buddyswitch-codex instance start --buddy pm --json
./buddyswitch-codex instance attach <new-instance-id>
```

Expected:

- If Codex has been updated to allow loaded unmaterialized thread resume: no `Failed to resume session from ...jsonl`, and TUI opens on the newly created instance thread.
- If Codex still matches `/Users/chen/Dev/codex` source reviewed above: this smoke is expected to remain blocked by `thread/resume` rejecting an unmaterialized thread. Record that as a Codex contract blocker instead of adding a BuddySwitch fallback.
- Exiting TUI leaves instance status `active` until explicit `instance stop` when the attach succeeds.

- [ ] **Step 2: Web active turn attach smoke**

Open:

```text
http://127.0.0.1:8765/
```

Use the page to send a long-running instruction to the selected instance. While the page shows `Thread State active`, run in a terminal:

```bash
./buddyswitch-codex instance attach <same-instance-id>
```

Expected:

- TUI shows the same running turn or its live event stream.
- `./buddyswitch-codex instance status <same-instance-id> --json` reports the same `thread_id` as the Web page.
- If the turn completes before attach opens, TUI still opens the same completed thread history.

- [ ] **Step 3: Clear then attach smoke**

Run:

```bash
./buddyswitch-codex instance clear <same-instance-id> --json
./buddyswitch-codex instance attach <same-instance-id>
```

Expected:

- If Task 0 proves Codex can resume loaded unmaterialized threads, attach opens the new `thread_id` returned by clear and no local replay path error appears.
- If current Codex still rejects unmaterialized threads, record this as the same Codex contract blocker.

### Task 9: Full Verification and Review

**Files:**

- No implementation edits.

- [ ] **Step 1: Full test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Review search**

Run:

```bash
rg -n 'buddyswitch_run_codex --remote|codex --remote|resume --remote' buddyswitch-codex tools/launcher tests docs/spec
rg -n 'thread/resume' tools/launcher/app_server.py tools/launcher/app_server.sh buddyswitch-codex tests
rg -n 'buddyswitch/objects|buddyswitch/local/buddybox' buddyswitch-codex tools/launcher tests/test_buddyswitch_launcher.py
rg -n 'shell=True|FastAPI|Flask|aiohttp|queue|workflow|plugin|auth' tools/launcher/app_server.py tools/launcher/app_server.sh buddyswitch-codex
git diff --stat
git diff
git status --short --branch
```

Expected:

- No `buddyswitch_run_codex --remote` remains for attach.
- `resume --remote` appears only for the intentional TUI attach path and docs/tests.
- `thread/resume` appears in app-server helper, shell wrapper, attach preflight, and tests.
- No direct runtime object or old buddybox path edits.
- No new framework/queue/workflow/auth complexity.

## Acceptance Criteria

- Active Web-started turns are visible from `instance attach`.
- Fresh empty Web-created threads can be attached without local JSONL replay errors only after Task 0 proves Codex supports resuming loaded unmaterialized threads.
- Clear-created fresh threads route to their new thread id; end-to-end attach succeeds under the same Codex unmaterialized-thread condition above.
- Attach still rejects missing thread id and unhealthy app-server.
- Attach does not stop the service when TUI exits.
- Web API contract remains unchanged.
- Full test suite passes.

## Notes for Implementers

- Do not use `path` in `thread/resume` params. The schema says path can override `threadId` for non-running threads; BuddySwitch should prefer `threadId`.
- Do not store active turn id in `instance.json`. Continue querying app-server for active turn details.
- Do not add a BuddySwitch transcript parser. Codex owns app-server thread history and TUI rendering.
- If `thread/resume` preflight fails for a fresh empty thread with `no rollout found for thread id`, treat it as the known Codex unmaterialized-thread contract blocker. Do not work around it in BuddySwitch.
- If `thread/resume` preflight succeeds but `codex resume --remote ... <thread_id>` still fails on fresh empty threads, stop and capture:
  - stderr from TUI launch
  - `thread/resume` response
  - `thread/read` response
  - generated Codex schema version
  Then revisit the CLI invocation instead of adding fallback replay logic.
