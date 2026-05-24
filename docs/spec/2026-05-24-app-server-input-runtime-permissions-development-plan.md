# App-server Input Runtime Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every new turn started by BuddySwitch `instance input` explicitly selects the `buddyswitch-runtime` permission profile.

**Architecture:** Keep the current app-server service-mode shape. Thread creation already selects the runtime profile; extend the same explicit permission selection to idle `turn/start` calls made by the input path. The launcher shell passes the profile to the Python app-server helper, and the helper refuses to run input without an explicit profile.

**Tech Stack:** Bash launcher helpers, Python app-server helper, Codex app-server JSON-RPC over Unix socket, pytest/unittest launcher tests.

---

## Scope

This plan covers the complete escaped-defect repair:

- regression tests for idle input turn permission propagation
- parser/helper coverage that prevents a silent no-permission helper path
- minimal launcher/helper implementation
- focused verification
- broader relevant verification
- final review scan

Do not implement:

- a new permission profile
- a generic permission framework
- Codex source changes
- runtime broker protocol changes
- taskbox, message, artifact, track, or buddybox behavior changes
- fallback to TUI, direct runtime files, or legacy object state

## Files To Modify

- `tests/test_buddyswitch_launcher.py`
  - assert start `thread/start` keeps `buddyswitch-runtime`
  - assert idle input `turn/start` includes `permissions: "buddyswitch-runtime"`
  - assert idle input `turn/start` does not include `sandboxPolicy`

- `tests/test_app_server_client.py`
  - add helper parser coverage so `input` requires explicit `--permissions`

- `tools/launcher/app_server.py`
  - add an explicit `permissions` argument to `input_turn`
  - include `permissions` in idle `turn/start` params
  - add required `--permissions` to the `input` subcommand
  - pass parsed permissions through `_command_input`

- `tools/launcher/app_server.sh`
  - pass `--permissions "buddyswitch-runtime"` from `buddyswitch_app_server_input`

No docs or runtime state files outside `docs/spec` should be required for the implementation itself.

## Required Contract

Idle `turn/start` from BuddySwitch input must send:

```json
{
  "threadId": "<thread-id>",
  "input": [
    {
      "type": "text",
      "text": "<user text>",
      "text_elements": []
    }
  ],
  "permissions": "buddyswitch-runtime"
}
```

It must not send:

```json
{
  "sandboxPolicy": {}
}
```

Active `turn/steer` remains unchanged.

## Implementation Tasks

### Task 1: Add Launcher Regression Test For Idle Input Permission

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Strengthen `test_input_starts_turn_when_thread_idle`**

Add these assertions after the existing `turn_start` lookup:

```python
self.assertEqual(turn_start["params"]["threadId"], ctx["instance_payload"]["thread_id"])
self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
self.assertNotIn("sandboxPolicy", turn_start["params"])
```

Keep the existing assertion for the text input payload:

```python
self.assertEqual(
    turn_start["params"]["input"],
    [{"type": "text", "text": "Draft brief", "text_elements": []}],
)
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_starts_turn_when_thread_idle -q
```

Expected before implementation:

```text
FAILED
```

The expected failure should be the missing `permissions` key or mismatched permission value.

### Task 2: Add Helper Parser Guard

**Files:**

- Modify: `tests/test_app_server_client.py`

- [ ] **Step 1: Add a parser test near the other app-server client tests**

Add:

```python
def test_input_command_requires_explicit_permissions_profile(self) -> None:
    parser = APP_SERVER.build_parser()
    with self.assertRaises(SystemExit):
        parser.parse_args(
            [
                "input",
                "--socket",
                "/tmp/app-server.sock",
                "--thread-id",
                "thread-1",
                "--text",
                "Draft brief",
            ]
        )

    args = parser.parse_args(
        [
            "input",
            "--socket",
            "/tmp/app-server.sock",
            "--thread-id",
            "thread-1",
            "--text",
            "Draft brief",
            "--permissions",
            "buddyswitch-runtime",
        ]
    )
    self.assertEqual(args.permissions, "buddyswitch-runtime")
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py::AppServerClientTests::test_input_command_requires_explicit_permissions_profile -q
```

Expected before implementation:

```text
FAILED
```

The no-permission parse currently succeeds, or the parser does not accept `--permissions`.

### Task 3: Confirm Start Path Still Sends Runtime Permission

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add baseline assertions to the service start test**

In `test_start_with_buddy_starts_app_server_service_and_returns`, add a call capture path before building `env`:

```python
calls_path = temp_root_path / "calls.jsonl"
env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
```

After the start command succeeds, add:

```python
call_entries = [
    json.loads(line)
    for line in calls_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
rpc_rows = [row for row in call_entries if row["argv"][:1] == ["json-rpc"]]
thread_start = next(row for row in rpc_rows if row["rpc_method"] == "thread/start")
self.assertEqual(thread_start["params"]["permissions"], "buddyswitch-runtime")
self.assertIn("runtimeWorkspaceRoots", thread_start["params"])
self.assertNotIn("sandboxPolicy", thread_start["params"])
```

- [ ] **Step 2: Run the focused baseline test**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_starts_app_server_service_and_returns -q
```

Expected:

```text
1 passed
```

If this fails, stop and inspect why thread creation lost the existing permission behavior before changing input.

### Task 4: Implement Explicit Input Permissions In Python Helper

**Files:**

- Modify: `tools/launcher/app_server.py`

- [ ] **Step 1: Change `input_turn` signature**

Replace:

```python
def input_turn(socket_path: Path, thread_id: str, text: str) -> dict[str, Any]:
```

with:

```python
def input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
    if not permissions:
        raise AppServerProtocolError("input turn requires an explicit permissions profile")
```

Keep the existing `thread_read(...)` call immediately after the validation.

- [ ] **Step 2: Add permissions to idle `turn/start` params**

Replace the idle request params:

```python
{
    "threadId": thread_id,
    "input": text_input_payload(text),
}
```

with:

```python
{
    "threadId": thread_id,
    "input": text_input_payload(text),
    "permissions": permissions,
}
```

Do not add `sandboxPolicy`.

- [ ] **Step 3: Pass CLI permissions through `_command_input`**

Replace:

```python
payload = input_turn(Path(args.socket), args.thread_id, args.text)
```

with:

```python
payload = input_turn(Path(args.socket), args.thread_id, args.text, args.permissions)
```

- [ ] **Step 4: Add required parser argument**

In the `input` subcommand parser, add:

```python
input_parser.add_argument("--permissions", required=True)
```

### Task 5: Pass Runtime Permission From Shell Launcher

**Files:**

- Modify: `tools/launcher/app_server.sh`

- [ ] **Step 1: Update `buddyswitch_app_server_input`**

Replace:

```bash
python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" input \
  --socket "$(buddyswitch_app_server_socket)" \
  --thread-id "${thread_id}" \
  --text "${text}"
```

with:

```bash
python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" input \
  --socket "$(buddyswitch_app_server_socket)" \
  --thread-id "${thread_id}" \
  --text "${text}" \
  --permissions "buddyswitch-runtime"
```

Do not add a configurable profile for this repair.

### Task 6: Focused Verification

- [ ] **Step 1: Run parser and idle input tests**

Run:

```bash
python3 -m pytest \
  tests/test_app_server_client.py::AppServerClientTests::test_input_command_requires_explicit_permissions_profile \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_starts_turn_when_thread_idle \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 2: Run active input behavior tests**

Run:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_steers_in_progress_turn \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_reports_non_steerable_active_turn \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 3: Run start baseline**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_starts_app_server_service_and_returns -q
```

Expected:

```text
1 passed
```

### Task 7: Broader Relevant Verification

- [ ] **Step 1: Run app-server and launcher suites**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run runtime permission and boundary suites**

Run:

```bash
python3 -m pytest \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_runless_runtime_contract.py \
  tests/test_runtime_broker.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

```text
all tests pass
```

### Task 8: Final Review

- [ ] **Step 1: Scan turn-start and permissions paths**

Run:

```bash
rg -n '"turn/start"|turn/start|input_turn|--permissions|buddyswitch-runtime' tools/launcher tests docs/spec
```

Review findings and confirm:

- every BuddySwitch-owned idle input `turn/start` includes `permissions`
- no `turn/start` includes both `permissions` and `sandboxPolicy`
- no direct write path to runtime durable state was added
- `turn/steer` behavior remains a steer path, not a duplicate start path

- [ ] **Step 2: Check git diff scope**

Run:

```bash
git diff -- tools/launcher/app_server.py tools/launcher/app_server.sh tests/test_app_server_client.py tests/test_buddyswitch_launcher.py
git status -sb
```

Expected:

- only the planned implementation/test files are changed
- any pre-existing user-owned dirty file remains untouched

## Completion Criteria

Report complete only after:

1. the idle input regression test failed before implementation
2. all focused tests pass after implementation
3. broader relevant verification passes
4. final scan finds no no-permission BuddySwitch input `turn/start`
5. review finds no fallback, migration, direct runtime state write, or unrelated product-semantic change
