# Launcher Web Init And Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation, then use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Web-created and Web-cleared BuddySwitch threads immediately attachable/resumable by materializing them with a fixed init turn, and add a launcher/Web resume path for stopped instances.

**Architecture:** Keep launcher commands atomic and keep lifecycle truth in the existing instance/app-server helpers. The launcher adds only `instance resume` for stopped instances; Web API owns product orchestration for start/clear initialization by sending a fixed `ready` prompt through existing launcher `instance input` and waiting until the turn is no longer active. The browser UI calls Web product actions only; it never builds the fixed init prompt.

**Tech Stack:** Bash launcher, Python standard-library Web API and subprocess runner, Python app-server JSON-RPC helper, vanilla JavaScript UI, `pytest`, Node built-in `assert`.

---

## Current Problem

Codex `thread/start` creates an in-memory thread id before the first user turn is persisted. Until a real `turn/start` happens, there is no rollout/session JSONL for `thread/resume` to load, so attach or stop-then-resume can fail with:

```text
no rollout found for thread id <thread-id>
```

This is a Codex contract, not a BuddySwitch parsing bug. BuddySwitch must not write JSONL, create fake turns, or duplicate Codex lifecycle. The product-level fix is to make Web-created threads send one explicit, low-side-effect initialization message and wait for it to complete.

## Scope

In scope:

- Add launcher command `instance resume <instance-id> [--json]`.
- Add Web API fixed initialization orchestration after Web start and Web clear.
- Add Web API retry route `POST /api/instances/<id>/initialize`.
- Add Web API route `POST /api/instances/<id>/clear`.
- Add Web API route `POST /api/instances/<id>/resume`.
- Add minimal UI controls for clear, initialize retry, and resume.
- Add requirement-driven tests at launcher, Web API, and UI state boundaries.
- Add manual smoke and review gates.

Out of scope:

- No launcher automatic init in `instance start` or `instance clear`.
- No JSONL writer, fake session, dummy local transcript, or fallback parser.
- No Web API for `goal` or `compact` in this task.
- No queue, workflow engine, plugin system, auth layer, remote service, or framework.
- No direct writes to `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`.
- No weakening or skipping existing tests.

## Fixed Web Init Prompt

Use this exact prompt as a Web API server-side constant:

```text
Initialize this BuddySwitch thread. Do not perform any task or use tools. Reply exactly: ready
```

The init prompt is intentionally stored in Web API server code, not in frontend JavaScript and not in the launcher. The resulting `ready` exchange is a real conversation turn and remains visible in the thread history.

Web should wait for the init turn to finish by polling launcher `instance status --json` until `thread.status` is no longer `active` or `in_progress`. Do not parse transcripts to verify the assistant text; that would reintroduce a second conversation-history truth. The success condition is that Codex accepted and completed the fixed init turn.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `instance resume <id> --json` restores an inactive stored instance using the original `thread_id`. |
| FR2 | `instance resume <id>` without `--json` prints concise human output and does not change existing human output for other commands. |
| FR3 | `instance resume` is idempotent for an already active healthy instance and returns the current active state without restarting lifecycle. |
| FR4 | `instance resume` blocks with exit code `3` when the instance has no `thread_id`. |
| FR5 | `instance resume` stops newly started resume resources and keeps the instance inactive if Codex `thread/resume` rejects the thread, including unmaterialized empty-thread failures. |
| FR6 | Resume uses existing app-server/browser/broker helpers and app-server `thread/resume`; it does not implement its own thread lifecycle. |
| FR7 | Web `POST /api/instances` runs launcher `start`, sends the fixed init prompt through launcher `input`, waits for init completion, then returns success. |
| FR8 | Web `POST /api/instances` returns an error if start succeeds but fixed init input fails or times out; it does not pretend the instance is ready. |
| FR9 | Web `POST /api/instances/<id>/clear` runs launcher `clear`, sends the fixed init prompt, waits for init completion, then returns the new `thread_id` and final instance status. |
| FR10 | Web `POST /api/instances/<id>/initialize` sends only the fixed init prompt and waits for completion. |
| FR11 | Web `POST /api/instances/<id>/resume` runs launcher `instance resume <id> --json` and returns refreshed status. |
| FR12 | Normal Web `input` continues to send user-provided text and does not use the fixed init prompt. |
| FR13 | Web action routes preserve structured HTTP errors for invalid request, lifecycle block, command failure, and command timeout. |
| FR14 | Browser UI exposes Resume for inactive instances, Clear for idle active instances, and Retry Initialize for active healthy idle instances. |
| FR15 | Browser UI does not embed or construct the fixed init prompt. |
| FR16 | Existing send, interrupt, stop, delete, create, list, and status behavior remains stable. |

## Coverage Matrix

| Requirement | Primary Tests |
| --- | --- |
| FR1 | `tests/test_buddyswitch_launcher.py::test_instance_resume_json_restarts_stopped_instance_with_original_thread` |
| FR2 | `tests/test_buddyswitch_launcher.py::test_instance_resume_human_output_reports_instance_and_thread` |
| FR3 | `tests/test_buddyswitch_launcher.py::test_instance_resume_active_instance_is_idempotent` |
| FR4 | `tests/test_buddyswitch_launcher.py::test_instance_resume_blocks_when_thread_id_missing` |
| FR5 | `tests/test_buddyswitch_launcher.py::test_instance_resume_keeps_inactive_when_thread_resume_fails` |
| FR6 | Review `rg` gate for forbidden lifecycle duplication and direct runtime writes. |
| FR7 | `tests/test_web_management.py::test_create_instance_initializes_thread_before_returning` |
| FR8 | `tests/test_web_management.py::test_create_instance_returns_error_when_initialization_fails` and timeout variant |
| FR9 | `tests/test_web_management.py::test_clear_route_initializes_new_thread_before_returning` |
| FR10 | `tests/test_web_management.py::test_initialize_route_sends_fixed_prompt_and_waits` |
| FR11 | `tests/test_web_management.py::test_resume_route_delegates_to_launcher_resume` |
| FR12 | Existing input tests plus `tests/test_web_management.py::test_user_input_does_not_use_fixed_init_prompt` |
| FR13 | Existing malformed JSON/command failure tests plus new init timeout/failure tests |
| FR14 | `tests/web_management_ui_state.test.js` action-state tests |
| FR15 | `rg` review gate: fixed init prompt exists only in `tools/launcher/web_management.py` and tests |
| FR16 | Existing focused launcher/Web/UI suites and full `pytest` |

## Files

- Modify: `buddyswitch-codex`
  - Add public `instance resume <instance-id> [--json]`.
  - Add locked resume entrypoint.
  - Keep `start`, `clear`, and `input` atomic; do not add fixed init prompt here.
- Modify: `tools/launcher/instance.sh`
  - Add usage and dispatcher entry for `resume`.
- Modify: `tools/launcher/env.sh`
  - Only if a focused test proves a small record-update helper is needed. Do not move lifecycle truth into a new abstraction.
- Modify: `tools/launcher/web_management.py`
  - Add fixed init prompt constant.
  - Add init-and-wait helper.
  - Add clear, initialize, and resume routes.
  - Update create route to initialize before success.
- Modify: `tools/launcher/assets/web-management/index.html`
  - Add buttons for Clear, Retry Initialize, and Resume.
- Modify: `tools/launcher/assets/web-management/app.js`
  - Extend action-state calculation and route calls.
- Modify: `tests/helpers/fake_codex.py`
  - Extend fake service support only if launcher resume tests need a deterministic `thread/resume` failure/success state not already available.
- Modify: `tests/test_buddyswitch_launcher.py`
  - Add launcher resume tests.
- Modify: `tests/test_web_management.py`
  - Add Web API orchestration tests.
- Modify: `tests/web_management_ui_state.test.js`
  - Add UI action-state tests for resume/clear/initialize.

## Testing Principles

- Tests must be written from functional behavior, not private helper names.
- Launcher lifecycle tests should stay at subprocess boundary and fake only external Codex/browser dependencies already faked by the suite.
- Web API tests may use the existing fake command runner because they test the Web-to-launcher contract, not Codex internals.
- UI tests should assert action availability and endpoint wiring, not CSS details.
- Do not add tests that pass by checking for a specific brittle internal implementation when an observable contract exists.

---

## Task 1: Launcher Resume Regression Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Possible test harness update: `tests/helpers/fake_codex.py`

- [ ] **Step 1: Add failing test for stopped materialized instance resume**

Add a launcher subprocess test using the existing service-mode helper that starts a fake app-server instance, sends one real input to materialize the thread in fake state, stops the instance, then resumes it:

```python
def test_instance_resume_json_restarts_stopped_instance_with_original_thread(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        instance_id = str(ctx["instance_id"])
        instance_payload = ctx["instance_payload"]
        assert isinstance(instance_payload, dict)
        thread_id = str(instance_payload["thread_id"])

        input_result = subprocess.run(
            [str(LAUNCHER), "instance", "input", instance_id, "--text", "materialize", "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)

        stop_result = subprocess.run(
            [str(LAUNCHER), "instance", "stop", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
        payload = json.loads(resume_result.stdout)
        self.assertEqual(payload["instance_id"], instance_id)
        self.assertEqual(payload["thread_id"], thread_id)
        self.assertEqual(payload["status"], "active")
        record = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(record["thread_id"], thread_id)
        self.assertEqual(record["status"], "active")
        self.assertIsInstance(record["app_server_pid"], int)
        self.assertTrue(record["app_server_socket"])
```

Expected RED: launcher reports unknown `resume` command.

- [ ] **Step 2: Add failing test that resume calls app-server `thread/resume` for the original thread**

Use the fake app-server call log already used by attach tests:

```python
def test_instance_resume_uses_thread_resume_for_original_thread(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        instance_id = str(ctx["instance_id"])
        instance_payload = ctx["instance_payload"]
        assert isinstance(instance_payload, dict)
        thread_id = str(instance_payload["thread_id"])
        subprocess.run(
            [str(LAUNCHER), "instance", "input", instance_id, "--text", "materialize", "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [str(LAUNCHER), "instance", "stop", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
        calls = [
            json.loads(line)
            for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        resume_calls = [row for row in calls if row.get("rpc_method") == "thread/resume"]
        self.assertTrue(resume_calls, "resume must use Codex app-server thread/resume")
        self.assertEqual(resume_calls[-1]["params"]["threadId"], thread_id)
        self.assertEqual(resume_calls[-1]["params"]["excludeTurns"], True)
```

Expected RED: no `resume` command exists.

- [ ] **Step 3: Add failing test for human output**

```python
def test_instance_resume_human_output_reports_instance_and_thread(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        instance_id = str(ctx["instance_id"])
        instance_payload = ctx["instance_payload"]
        assert isinstance(instance_payload, dict)
        thread_id = str(instance_payload["thread_id"])
        subprocess.run(
            [str(LAUNCHER), "instance", "input", instance_id, "--text", "materialize", "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [str(LAUNCHER), "instance", "stop", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
        self.assertIn(f"Instance resumed: {instance_id}", resume_result.stdout)
        self.assertIn(f"Thread: {thread_id}", resume_result.stdout)
```

Expected RED: no `resume` command exists.

- [ ] **Step 4: Add failing test for active idempotency**

```python
def test_instance_resume_active_instance_is_idempotent(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        instance_id = str(ctx["instance_id"])
        record_path = Path(str(ctx["instance_root"])) / "instance.json"
        before = json.loads(record_path.read_text(encoding="utf-8"))
        thread_id = str(before["thread_id"])

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
        payload = json.loads(resume_result.stdout)
        self.assertEqual(payload["instance_id"], instance_id)
        self.assertEqual(payload["thread_id"], thread_id)
        self.assertEqual(payload["status"], "active")
        after = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(after["thread_id"], before["thread_id"])
        self.assertEqual(after["app_server_socket"], before["app_server_socket"])
```

Expected RED: no `resume` command exists.

- [ ] **Step 5: Add failing test for missing thread id block**

Create an inactive instance record with no `thread_id`, then run resume:

```python
def test_instance_resume_blocks_when_thread_id_missing(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        source_home_path = Path(source_home)
        shared_root = source_home_path / ".codex-buddyswitch"
        instance_id = "inst-pm-no-thread"
        self._write_instance_record(
            shared_root,
            instance_id,
            status="inactive",
            thread_id=None,
        )
        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id, "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(resume_result.returncode, 3)
        self.assertIn("has no thread id", resume_result.stderr)
```

Expected RED: no `resume` command exists.

- [ ] **Step 6: Add failing test for `thread/resume` failure cleanup**

Configure the fake app-server so `thread/resume` fails with `no rollout found for thread id <id>`, then assert resume fails and keeps the record inactive:

```python
def test_instance_resume_keeps_inactive_when_thread_resume_fails(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home), buddy="pm")
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        instance_id = str(ctx["instance_id"])
        instance_payload = ctx["instance_payload"]
        assert isinstance(instance_payload, dict)
        thread_id = str(instance_payload["thread_id"])
        subprocess.run(
            [str(LAUNCHER), "instance", "stop", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        Path(str(ctx["state_file"])).write_text(
            json.dumps(
                {
                    "thread_id": thread_id,
                    "errors": {
                        "thread/resume": {
                            "code": -32600,
                            "message": f"no rollout found for thread id {thread_id}",
                        }
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        resume_result = subprocess.run(
            [str(LAUNCHER), "instance", "resume", instance_id, "--json"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(resume_result.returncode, 0)
        self.assertIn("thread/resume failed", resume_result.stderr)
        record = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "inactive")
        self.assertIsNone(record.get("app_server_pid"))
        self.assertIsNone(record.get("app_server_socket"))
```

Expected RED: no `resume` command exists. Existing fake Codex already supports configured `errors` in the app-server state file; do not add new fake behavior unless the focused test proves the current error injection does not cover resumed app-server processes.

- [ ] **Step 7: Run launcher resume tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_resume' -q
```

Expected: FAIL because launcher resume is not implemented.

## Task 2: Implement Launcher Resume

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/env.sh` only if a narrowly scoped helper is needed

- [ ] **Step 1: Add command usage and dispatcher**

Update both top-level help in `buddyswitch-codex` and instance usage in `tools/launcher/instance.sh` with:

```text
buddyswitch-codex instance resume <instance-id> [--json]
```

Route `instance resume` to a new `instance_resume "$@"` function in `buddyswitch-codex`.

- [ ] **Step 2: Add locked resume entrypoint**

Add an internal dispatcher arm:

```bash
__locked-instance-resume)
  shift || true
  instance_resume_locked "$@"
  ;;
```

`instance_resume` should parse `<instance-id>` and `--json`, validate the record, and call:

```bash
buddyswitch_with_runtime_lock \
  "${REPO_ROOT}/buddyswitch-codex" \
  "__locked-instance-resume" \
  "${instance_id}"
```

- [ ] **Step 3: Implement active idempotency**

Inside `instance_resume_locked`:

```bash
buddyswitch_require_runtime_lock
buddyswitch_validate_instance_id "${instance_id}" || return $?
buddy="$(buddyswitch_instance_validate_record "${instance_id}")" || return $?
buddyswitch_env_bind_instance "${instance_id}" || return $?
thread_id="$(buddyswitch_instance_record_field "${instance_id}" "thread_id" || true)"
if [[ -z "${thread_id}" ]]; then
  echo "Instance resume blocked: ${instance_id} has no thread id; delete it and start a new instance." >&2
  return 3
fi
if buddyswitch_app_server_is_active; then
  INSTANCE_RESUME_THREAD_ID="${thread_id}"
  INSTANCE_RESUME_STATUS="active"
  return 0
fi
```

Do not restart an already healthy active app-server.

- [ ] **Step 4: Implement inactive resume using existing helpers**

For inactive/unhealthy instances:

```bash
buddyswitch_ensure_shared_env
buddyswitch_workspace_ensure_project_worktree
buddyswitch_workspace_repair_runtime_projects_app_projection
buddyswitch_instance_ensure_private_writable_surface
buddyswitch_instance_ensure_taskbox "${buddy}"
buddyswitch_runtime_broker_ensure
buddyswitch_patch_codex_config
```

Then restore browser port:

```bash
browser_port="$(buddyswitch_instance_record_field "${instance_id}" "browser_port" || true)"
if [[ -n "${browser_port}" ]]; then
  export BUDDYSWITCH_BROWSER_PORT="${browser_port}"
else
  buddyswitch_browser_allocate_instance_port || return $?
fi
```

Bootstrap browser and app-server using existing helpers:

```bash
if ! buddyswitch_browser_bootstrap; then
  buddyswitch_runtime_broker_stop
  return 1
fi
buddyswitch_instance_set_browser_port "${instance_id}" "${BUDDYSWITCH_BROWSER_PORT}"
app_server_json="$(buddyswitch_app_server_ensure)" || { cleanup; return 1; }
```

Run:

```bash
resume_json="$(buddyswitch_app_server_thread_resume "${thread_id}" 2>&1)" || {
  echo "thread/resume failed for ${thread_id}" >&2
  [[ -n "${resume_json}" ]] && echo "${resume_json}" >&2
  buddyswitch_app_server_stop || true
  buddyswitch_runtime_broker_stop
  buddyswitch_browser_instance_stop "${instance_id}" || true
  buddyswitch_instance_clear_app_server "${instance_id}" "inactive"
  return 1
}
```

Parse `resume_json` and require the returned `thread.id` to equal `thread_id`. If it does not, clean up the newly started resources and return `1`.

Finally call:

```bash
buddyswitch_instance_set_app_server \
  "${instance_id}" \
  "${thread_id}" \
  "$(_buddyswitch_app_server_json_field "${app_server_json}" "pid")" \
  "$(_buddyswitch_app_server_json_field "${app_server_json}" "socket_path")" \
  "$(_buddyswitch_app_server_json_field "${app_server_json}" "log_file")" \
  "active"
```

- [ ] **Step 5: Emit JSON and human output**

`--json` output:

```json
{"instance_id":"inst-pm-...","thread_id":"019...","status":"active"}
```

Human output:

```text
Instance resumed: inst-pm-...
Thread: 019...
```

- [ ] **Step 6: Run launcher resume tests until GREEN**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_resume' -q
```

Expected: PASS.

## Task 3: Web API Initialization Tests

**Files:**

- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Add ordered command-runner test helpers**

The existing `FakeRunner` maps one response per command tuple and cannot model repeated `instance status` calls with changing thread states. Add ordered helpers near `FakeRunner`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandStep:
    args: list[str]
    result: WEB_MANAGEMENT.CommandResult


def command_json(payload: dict[str, object]) -> WEB_MANAGEMENT.CommandResult:
    return WEB_MANAGEMENT.CommandResult(
        returncode=0,
        stdout=json.dumps(payload, ensure_ascii=True),
        stderr="",
        timed_out=False,
    )


def command_error(*, returncode: int, stderr: str, timed_out: bool = False) -> WEB_MANAGEMENT.CommandResult:
    return WEB_MANAGEMENT.CommandResult(returncode=returncode, stdout="", stderr=stderr, timed_out=timed_out)


def active_status(instance_id: str, thread_id: str, thread_status: str) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "buddy": "pm",
        "status": "active",
        "workspace_dir": f"/tmp/shared/instances/{instance_id}/workspace",
        "browser_port": 9222,
        "updated_at": "2026-05-25T10:00:00Z",
        "thread_id": thread_id,
        "app_server": {"healthy": True},
        "thread": {"status": thread_status, "raw": {}},
    }


class OrderedRunner:
    def __init__(self, steps: list[CommandStep]) -> None:
        self.steps = list(steps)
        self.calls: list[tuple[list[str], float]] = []

    def run(self, args: list[str], *, timeout_seconds: float) -> WEB_MANAGEMENT.CommandResult:
        self.calls.append((list(args), timeout_seconds))
        if not self.steps:
            raise AssertionError(f"unexpected command with no steps left: {args!r}")
        step = self.steps.pop(0)
        if step.args != args:
            raise AssertionError(f"expected command {step.args!r}, got {args!r}")
        return step.result
```

- [ ] **Step 2: Add test for create start + fixed init + wait**

Use the existing fake command runner style. The test should assert the observable command sequence:

```python
def test_create_instance_initializes_thread_before_returning(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(["instance", "buddies", "--json"], command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]})),
            CommandStep(["instance", "start", "--buddy", "pm", "--json"], command_json({"instance_id": "inst-pm-demo"})),
            CommandStep(
                ["instance", "input", "inst-pm-demo", "--text", WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, "--json"],
                command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-1", "action": "start", "turn_id": "turn-init"}),
            ),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-1", "active"))),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-1", "idle"))),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["instance_id"], "inst-pm-demo")
    self.assertEqual(payload["turn_id"], "turn-init")
    self.assertEqual(payload["instance"]["thread"]["status"], "idle")
    self.assertEqual(runner.calls[2][0], ["instance", "input", "inst-pm-demo", "--text", WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, "--json"])
    self.assertEqual(runner.steps, [])
```

- [ ] **Step 3: Add test for create init command failure**

```python
def test_create_instance_returns_error_when_initialization_fails(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(["instance", "buddies", "--json"], command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]})),
            CommandStep(["instance", "start", "--buddy", "pm", "--json"], command_json({"instance_id": "inst-pm-demo"})),
            CommandStep(
                ["instance", "input", "inst-pm-demo", "--text", WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, "--json"],
                command_error(returncode=1, stderr="model failed"),
            ),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
        service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

    self.assertEqual(raised.exception.status, 502)
    self.assertEqual(raised.exception.code, "COMMAND_FAILED")
    self.assertIn("model failed", raised.exception.message)
```

- [ ] **Step 4: Add test for create init wait timeout**

The fake runner should return active status repeatedly until the Web wait timeout is exceeded. Make the timeout configurable in the service constructor for tests:

```python
service = WEB_MANAGEMENT.WebManagementService(
    repo_root=ROOT,
    command_runner=runner.run,
    init_wait_timeout_seconds=0.01,
    init_wait_poll_seconds=0.001,
)
```

Expected error:

```python
self.assertEqual(raised.exception.status, 504)
self.assertEqual(raised.exception.code, "COMMAND_TIMEOUT")
self.assertIn("Initialization did not finish", raised.exception.message)
```

- [ ] **Step 5: Add test for clear route initialization**

```python
def test_clear_route_initializes_new_thread_before_returning(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "clear", "inst-pm-demo", "--json"],
                command_json({"instance_id": "inst-pm-demo", "previous_thread_id": "thread-old", "thread_id": "thread-new"}),
            ),
            CommandStep(
                ["instance", "input", "inst-pm-demo", "--text", WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, "--json"],
                command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-new", "action": "start", "turn_id": "turn-init"}),
            ),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-new", "idle"))),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/clear", b"")

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["previous_thread_id"], "thread-old")
    self.assertEqual(payload["thread_id"], "thread-new")
    self.assertEqual(payload["turn_id"], "turn-init")
    self.assertEqual(payload["instance"]["thread_id"], "thread-new")
```

- [ ] **Step 6: Add test for initialize retry route**

```python
def test_initialize_route_sends_fixed_prompt_and_waits(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "input", "inst-pm-demo", "--text", WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, "--json"],
                command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-1", "action": "start", "turn_id": "turn-init"}),
            ),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-1", "idle"))),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/initialize", b"")

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["turn_id"], "turn-init")
    self.assertEqual(payload["instance"]["thread"]["status"], "idle")
```

- [ ] **Step 7: Add test for resume route**

```python
def test_resume_route_delegates_to_launcher_resume(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(["instance", "resume", "inst-pm-demo", "--json"], command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-1", "status": "active"})),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-1", "idle"))),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/resume", b"")

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["instance"]["status"], "active")
    self.assertEqual(runner.calls[0][0], ["instance", "resume", "inst-pm-demo", "--json"])
```

- [ ] **Step 8: Add regression test that normal input does not use fixed init prompt**

```python
def test_user_input_does_not_use_fixed_init_prompt(self) -> None:
    runner = OrderedRunner(
        [
            CommandStep(
                ["instance", "input", "inst-pm-demo", "--text", "User task", "--json"],
                command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-1", "action": "start", "turn_id": "turn-user"}),
            ),
            CommandStep(["instance", "status", "inst-pm-demo", "--json"], command_json(active_status("inst-pm-demo", "thread-1", "active"))),
        ]
    )
    service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

    status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/input", b'{"text":"User task"}')

    self.assertEqual(status, 200)
    self.assertEqual(payload["turn_id"], "turn-user")
    self.assertNotIn(WEB_MANAGEMENT.INITIALIZE_THREAD_PROMPT, json.dumps(runner.calls))
```

- [ ] **Step 9: Run Web API tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: FAIL because clear, initialize, resume, and create initialization are not implemented.

## Task 4: Implement Web API Initialization And Resume

**Files:**

- Modify: `tools/launcher/web_management.py`

- [ ] **Step 1: Add constants**

Add near existing module constants:

```python
INITIALIZE_THREAD_PROMPT = "Initialize this BuddySwitch thread. Do not perform any task or use tools. Reply exactly: ready"
ACTIVE_THREAD_STATUSES = {"active", "in_progress"}
DEFAULT_INIT_WAIT_TIMEOUT_SECONDS = 120.0
DEFAULT_INIT_WAIT_POLL_SECONDS = 0.25
```

Also add `import time`.

- [ ] **Step 2: Add test-configurable wait settings**

Extend `WebManagementService.__init__`:

```python
def __init__(
    self,
    *,
    repo_root: Path,
    command_runner: Callable[[list[str], float], CommandResult] | Callable[..., CommandResult] | None = None,
    busy_guard: BusyGuard | None = None,
    init_wait_timeout_seconds: float = DEFAULT_INIT_WAIT_TIMEOUT_SECONDS,
    init_wait_poll_seconds: float = DEFAULT_INIT_WAIT_POLL_SECONDS,
) -> None:
    ...
    self._init_wait_timeout_seconds = init_wait_timeout_seconds
    self._init_wait_poll_seconds = init_wait_poll_seconds
```

- [ ] **Step 3: Add route parsing**

Extend `handle_api` and `_parse_instance_action_path`:

```python
if method == "POST" and action == "clear":
    return 200, self._clear(instance_id)
if method == "POST" and action == "initialize":
    return 200, self._initialize(instance_id)
if method == "POST" and action == "resume":
    return 200, self._resume(instance_id)
```

Parse `/clear`, `/initialize`, and `/resume` before the catch-all delete path.

- [ ] **Step 4: Add fixed init helper**

Add a private helper that does not acquire the busy guard by itself:

```python
def _run_initialize_under_lock(self, instance_id: str) -> dict[str, Any]:
    parsed = self._run_input_command(instance_id, INITIALIZE_THREAD_PROMPT, timeout_seconds=60)
    final_status = self._wait_for_instance_idle(instance_id)
    payload: dict[str, Any] = {"ok": True, "instance": final_status}
    turn_id = parsed.get("turn_id")
    action = parsed.get("action")
    if isinstance(turn_id, str):
        payload["turn_id"] = turn_id
    if isinstance(action, str):
        payload["action"] = action
    return payload
```

Extract the existing launcher input call from `_send_input_under_lock` into:

```python
def _run_input_command(self, instance_id: str, text: str, *, timeout_seconds: float) -> dict[str, Any]:
    result = self._run_command(
        ["instance", "input", instance_id, "--text", text, "--json"],
        timeout_seconds=timeout_seconds,
    )
    return load_command_json_object(
        result.stdout,
        message=f"Invalid JSON from instance input for {instance_id}.",
    )
```

Keep `_send_input_under_lock` returning immediate status after user input. Do not wait for user input completion in this task.

- [ ] **Step 5: Add wait helper**

```python
def _wait_for_instance_idle(self, instance_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + self._init_wait_timeout_seconds
    last_status: dict[str, Any] | None = None
    while True:
        last_status = self._get_instance_status(instance_id)
        thread = last_status.get("thread") if isinstance(last_status.get("thread"), dict) else {}
        thread_status = thread.get("status") if isinstance(thread, dict) else None
        if not isinstance(thread_status, str) or thread_status not in ACTIVE_THREAD_STATUSES:
            return last_status
        if time.monotonic() >= deadline:
            raise HttpError(
                status=504,
                code="COMMAND_TIMEOUT",
                message=f"Initialization did not finish for {instance_id}.",
            )
        time.sleep(self._init_wait_poll_seconds)
```

This helper does not inspect transcript content.

- [ ] **Step 6: Update create route**

After successful launcher start and valid `instance_id`, call `_run_initialize_under_lock(instance_id)`. Return the initialized payload plus `instance_id`:

```python
init_payload = self._run_initialize_under_lock(instance_id)
init_payload["instance_id"] = instance_id
return init_payload
```

- [ ] **Step 7: Add clear route**

```python
def _clear(self, instance_id: str) -> dict[str, Any]:
    return self._run_busy(
        f"instance:{instance_id}",
        lambda: self._clear_under_lock(instance_id),
    )

def _clear_under_lock(self, instance_id: str) -> dict[str, Any]:
    result = self._run_command(["instance", "clear", instance_id, "--json"], timeout_seconds=60)
    cleared = load_command_json_object(
        result.stdout,
        message=f"Invalid JSON from instance clear for {instance_id}.",
    )
    init_payload = self._run_initialize_under_lock(instance_id)
    previous_thread_id = cleared.get("previous_thread_id")
    thread_id = cleared.get("thread_id")
    if isinstance(previous_thread_id, str):
        init_payload["previous_thread_id"] = previous_thread_id
    if isinstance(thread_id, str):
        init_payload["thread_id"] = thread_id
    return init_payload
```

- [ ] **Step 8: Add initialize retry route**

```python
def _initialize(self, instance_id: str) -> dict[str, Any]:
    return self._run_busy(
        f"instance:{instance_id}",
        lambda: self._run_initialize_under_lock(instance_id),
    )
```

- [ ] **Step 9: Add resume route**

```python
def _resume(self, instance_id: str) -> dict[str, Any]:
    return self._run_busy(
        f"instance:{instance_id}",
        lambda: self._resume_under_lock(instance_id),
    )

def _resume_under_lock(self, instance_id: str) -> dict[str, Any]:
    result = self._run_command(["instance", "resume", instance_id, "--json"], timeout_seconds=120)
    load_command_json_object(
        result.stdout,
        message=f"Invalid JSON from instance resume for {instance_id}.",
    )
    return {"ok": True, "instance": self._get_instance_status(instance_id)}
```

- [ ] **Step 10: Run Web API tests until GREEN**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: PASS.

## Task 5: UI State And Endpoint Tests

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/index.html`

- [ ] **Step 1: Add failing UI action-state tests**

Update expected state objects to include `canClear`, `canInitialize`, and `canResume`.

Add tests:

```javascript
test('inactive instance allows resume and delete only', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'inactive',
        app_server_health: 'unhealthy',
        thread: { status: 'idle' },
      },
      { draftText: 'Advance', isMutating: false }
    ),
    {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: true,
      canClear: false,
      canInitialize: false,
      canResume: true,
    }
  );
});

test('active idle instance allows clear and initialize retry', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      { draftText: '', isMutating: false }
    ),
    {
      canSend: false,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canInitialize: true,
      canResume: false,
    }
  );
});

test('active in-progress instance disables clear and initialize while allowing interrupt', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      { draftText: 'Steer', isMutating: false }
    ),
    {
      canSend: true,
      canInterrupt: true,
      canStop: true,
      canDelete: false,
      canClear: false,
      canInitialize: false,
      canResume: false,
    }
  );
});
```

Expected RED: current action state has no new keys.

- [ ] **Step 2: Implement action-state keys**

Update `computeInstanceActionState` to include:

```javascript
const threadBusy = threadStatus === 'active' || threadStatus === 'in_progress';
return {
  canSend: isActive && appServerHealthy && draftText.length > 0,
  canInterrupt: isActive && appServerHealthy && threadBusy,
  canStop: isActive,
  canDelete: isInactive,
  canClear: isActive && appServerHealthy && !threadBusy,
  canInitialize: isActive && appServerHealthy && !threadBusy,
  canResume: isInactive,
};
```

The no-selection and mutating-disabled branches must return all seven keys.

- [ ] **Step 3: Add UI buttons**

In `index.html`, add buttons near existing instance actions:

```html
<button id="clear-button" type="button">Clear</button>
<button id="initialize-button" type="button">Retry Initialize</button>
<button id="resume-button" type="button">Resume</button>
```

Keep styling consistent with existing buttons. Do not add explanatory in-app text for internal mechanics.

- [ ] **Step 4: Wire buttons to Web API routes**

In `app.js`, add elements:

```javascript
clearButton: document.getElementById('clear-button'),
initializeButton: document.getElementById('initialize-button'),
resumeButton: document.getElementById('resume-button'),
```

In `render`, set:

```javascript
elements.clearButton.disabled = !actionState.canClear;
elements.initializeButton.disabled = !actionState.canInitialize;
elements.resumeButton.disabled = !actionState.canResume;
```

Add event listeners:

```javascript
elements.clearButton.addEventListener('click', function () {
  runMutation(state, elements, 'clear', function () {
    return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/clear', {
      method: 'POST',
    });
  });
});

elements.initializeButton.addEventListener('click', function () {
  runMutation(state, elements, 'initialize', function () {
    return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/initialize', {
      method: 'POST',
    });
  });
});

elements.resumeButton.addEventListener('click', function () {
  runMutation(state, elements, 'resume', function () {
    return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/resume', {
      method: 'POST',
    });
  });
});
```

- [ ] **Step 5: Run UI tests until GREEN**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: all UI state tests pass.

## Task 6: Focused Regression

**Files:** no new files unless failures identify a root cause.

- [ ] **Step 1: Run launcher resume and existing lifecycle focused tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_resume or start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_ or clear_json_starts_clear_thread_and_updates_instance_record' -q
```

Expected: PASS.

- [ ] **Step 2: Run Web API focused tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: PASS.

- [ ] **Step 3: Run UI state tests**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: PASS.

- [ ] **Step 4: Run app-server client regression**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected: PASS.

## Task 7: Manual Smoke

**Files:** no code changes.

- [ ] **Step 1: Start Web server**

Run:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

If port `8765` is occupied, stop the existing BuddySwitch Web server or ask the user before using another port.

- [ ] **Step 2: Web start materializes and attach works**

In `http://127.0.0.1:8765/`, create a `pm` instance.

Expected:

- Create button remains busy until fixed init turn finishes.
- Created instance status becomes active and thread state is not active/in-progress.
- Run:

```bash
./buddyswitch-codex instance attach <instance-id>
```

Expected: TUI opens on the same thread instead of failing with `no rollout found`.

- [ ] **Step 3: Web clear materializes and attach works**

Click Clear on the active idle instance.

Expected:

- Clear action waits until fixed init turn finishes.
- Instance `thread_id` changes.
- `instance attach <instance-id>` opens the new thread instead of failing with `no rollout found`.

- [ ] **Step 4: Stop, resume, attach**

Click Stop, then Resume.

Expected:

- Stop makes instance inactive/unhealthy.
- Resume makes the same instance active/healthy.
- `thread_id` remains the same as before stop.
- `instance attach <instance-id>` opens the same resumed thread.

- [ ] **Step 5: Initialize retry**

If a real init failure is not easy to force without changing code, verify the API route directly on an already active idle instance:

```bash
curl -sS -X POST http://127.0.0.1:8765/api/instances/<instance-id>/initialize | python3 -m json.tool
```

Expected: JSON response has `ok: true`, a `turn_id`, and an active instance with non-busy thread status. If the model is unavailable or the command times out, record the exact error and ask the user whether to retry or stop.

## Task 8: Full Verification

**Files:** no code changes unless failures reveal root cause.

- [ ] **Step 1: Run required focused tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_resume or start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_ or clear_json_starts_clear_thread_and_updates_instance_record' -q
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Expected: all PASS.

- [ ] **Step 2: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS. If this is slow but still progressing, let it finish. If it stalls abnormally or fails in an unrelated existing area, capture the exact failure and ask the user before proceeding.

## Task 9: Final Review Gate

**Files:** no code changes unless review finds a real issue.

- [ ] **Step 1: Search for forbidden old parser/fallback patterns**

Run:

```bash
rg -n 'parse_buddies_tsv|parse_instance_list_tsv|parse_started_instance_id|parse_turn_action_output|parse_interrupt_turn_id' tools/launcher/web_management.py tests/test_web_management.py
```

Expected: no matches.

- [ ] **Step 2: Confirm init prompt ownership**

Run:

```bash
rg -n 'Initialize this BuddySwitch thread|Reply exactly: ready|INITIALIZE_THREAD_PROMPT' tools/launcher tests
```

Expected: production prompt appears in `tools/launcher/web_management.py`; tests may reference the exported constant. It must not appear in `tools/launcher/assets/web-management/app.js`.

- [ ] **Step 3: Confirm no direct runtime object/buddybox writes**

Run:

```bash
rg -n 'buddyswitch/objects|buddyswitch/local/buddybox' buddyswitch-codex tools/launcher tests/test_buddyswitch_launcher.py tests/test_web_management.py
```

Expected: no new direct-write logic. Existing path references in tests or docs are acceptable only if they are not runtime mutation paths.

- [ ] **Step 4: Confirm no unnecessary frameworks or risky shell**

Run:

```bash
rg -n 'shell=True|FastAPI|Flask|aiohttp|queue|workflow|plugin|auth' tools/launcher/web_management.py tools/launcher/app_server.py tools/launcher/app_server.sh buddyswitch-codex
```

Expected: no new framework/queue/workflow/plugin/auth additions and no `shell=True`. Existing help text mentioning auth bootstrap is acceptable.

- [ ] **Step 5: Inspect diff**

Run:

```bash
git diff --stat
git diff
git status --short --branch
```

Review must confirm:

- Only necessary launcher, Web API, UI, tests, and this spec changed.
- Launcher resume wraps existing lifecycle helpers and Codex `thread/resume`.
- Launcher `start` and `clear` remain atomic and do not send init prompt.
- Fixed init prompt lives in Web API server code, not frontend or launcher.
- Web start/clear wait for init completion before success.
- No JSONL writer, dummy transcript, fallback parser, or duplicated lifecycle truth.
- Human CLI default output remains covered.
- No skipped/loosened assertions.
- UI HTTP contract remains stable for existing actions.

## Required Final Report

The final implementation report must include:

- Implemented capabilities.
- Changed files.
- Focused test results with commands.
- Full `python3 -m pytest -q` result.
- Manual smoke result, including start attach, clear attach, stop resume attach, and initialize retry.
- Review gate conclusion.
- Any abnormal failure, skipped verification, environment issue, port issue, or risk that needs user confirmation.

Do not claim complete unless focused tests, full suite, manual smoke or explicitly accepted blocker handling, and final review all pass.
