# App-server Input Runtime Permissions Test Plan

Date: 2026-05-24

## Test Goal

Prove that every new Codex app-server turn created by BuddySwitch `instance input` keeps the BuddySwitch runtime permission profile and therefore remains able to use the runtime broker and env tools.

Tests must start from functional requirements: a buddy launched by BuddySwitch must keep the same runtime capability across later user inputs. Tests must not be written only to match the current function layout.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `instance start --buddy <buddy>` creates the thread with `permissions: "buddyswitch-runtime"` and the required runtime workspace roots. |
| FR2 | `instance input <id> --text <text>` starts a new turn with `permissions: "buddyswitch-runtime"` when the thread is idle. |
| FR3 | Idle `turn/start` includes Codex-compatible text input and does not include a conflicting `sandboxPolicy`. |
| FR4 | The permission profile reaches the BuddySwitch Python app-server helper through the launcher path, not only through direct unit calls. |
| FR5 | Missing permission propagation is treated as a test failure; there is no accepted no-permission input path. |
| FR6 | Active steerable turns continue to use `turn/steer` with `expectedTurnId` and do not create duplicate `turn/start` calls. |
| FR7 | Active non-steerable turns still fail clearly and do not fall back to `turn/start`. |
| FR8 | Inactive or unhealthy instances still fail before any app-server mutating call. |
| FR9 | Generated Codex config still defines and selects `buddyswitch-runtime`, including the runtime broker Unix socket allow-list. |
| FR10 | `instance attach` remains a remote TUI client and is not treated as a separate permission model. |
| FR11 | The fix does not write or mirror runtime durable state directly under `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | Launcher start test inspects fake app-server `thread/start` JSON-RPC params. |
| FR2 | Launcher input-idle test inspects fake app-server `turn/start` JSON-RPC params. |
| FR3 | Same input-idle test asserts payload shape and absence of `sandboxPolicy`. |
| FR4 | CLI-level `instance input` test, not only direct Python function tests. |
| FR5 | Helper CLI/parser test fails if `--permissions` is omitted. |
| FR6 | Existing active steering test remains in the focused run. |
| FR7 | Existing non-steerable active-turn test remains in the focused run. |
| FR8 | Existing inactive/unhealthy input test remains in the broader run. |
| FR9 | Existing config assertions plus start test remain in broader run. |
| FR10 | Existing attach test remains in broader run. |
| FR11 | Repo consistency/runtime boundary tests remain in broader run. |

## Test Data And Fakes

Use the existing Codex boundary fake in `tests/helpers/fake_codex.py`. This fake is appropriate because the BuddySwitch contract is the app-server JSON-RPC protocol, not real model behavior.

The fake must capture JSON-RPC method and params for:

- `thread/start`
- `thread/read`
- `thread/turns/list`
- `turn/start`
- `turn/steer`

The tests should assert behavior from the captured JSON-RPC records because the user-visible requirement is what BuddySwitch sends to Codex app-server.

## Test Changes

### 1. Start Preserves Runtime Permission Profile

Modify:

- `tests/test_buddyswitch_launcher.py`

Strengthen `test_start_with_buddy_starts_app_server_service_and_returns`:

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

Expected before implementation:

- This should already pass if the current start path is intact.

Purpose:

- Guard the baseline thread permission selection while fixing later input turns.

Focused command:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_starts_app_server_service_and_returns -q
```

### 2. Idle Input Starts Turn With Runtime Permission Profile

Modify:

- `tests/test_buddyswitch_launcher.py`

Strengthen `test_input_starts_turn_when_thread_idle`:

```python
turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
self.assertEqual(turn_start["params"]["threadId"], ctx["instance_payload"]["thread_id"])
self.assertEqual(
    turn_start["params"]["input"],
    [{"type": "text", "text": "Draft brief", "text_elements": []}],
)
self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
self.assertNotIn("sandboxPolicy", turn_start["params"])
```

Expected before implementation:

```text
FAILED ... KeyError: 'permissions'
```

or:

```text
AssertionError: None != 'buddyswitch-runtime'
```

Purpose:

- This is the escaped-defect regression test. It proves a later `instance input` turn does not degrade to read-only by omitting permission selection.

Focused command:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_starts_turn_when_thread_idle -q
```

### 3. App-server Helper CLI Does Not Accept Silent No-permission Input

Modify:

- `tests/test_app_server_client.py`

Add a focused test for the helper parser contract:

```python
parser = APP_SERVER.build_parser()
with self.assertRaises(SystemExit):
    parser.parse_args([
        "input",
        "--socket",
        "/tmp/app-server.sock",
        "--thread-id",
        "thread-1",
        "--text",
        "Draft brief",
    ])
```

Then assert the complete form parses:

```python
args = parser.parse_args([
    "input",
    "--socket",
    "/tmp/app-server.sock",
    "--thread-id",
    "thread-1",
    "--text",
    "Draft brief",
    "--permissions",
    "buddyswitch-runtime",
])
self.assertEqual(args.permissions, "buddyswitch-runtime")
```

Expected before implementation:

- The first parse does not fail because `--permissions` is not required.
- The complete form fails or does not expose `args.permissions`.

Purpose:

- Prevent direct helper usage from retaining the old no-permission path.

Focused command:

```bash
python3 -m pytest tests/test_app_server_client.py -k "permissions or parser" -q
```

### 4. Active Steering Remains Unchanged

Modify:

- No product behavior change expected.
- Keep existing assertions in `tests/test_buddyswitch_launcher.py`.

Run:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_steers_in_progress_turn \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_reports_non_steerable_active_turn \
  -q
```

Expected:

- Both pass.
- `turn/steer` includes `expectedTurnId`.
- No fallback `turn/start` is sent while active.

### 5. Runtime Config Boundary Remains Intact

Modify:

- No code change expected unless a regression appears.

Run:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_prepares_clean_runtime_workspace_and_tool_surface \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  -q
```

Expected:

- Generated Codex config still selects `buddyswitch-runtime`.
- Runtime broker socket remains allowed.
- Workspace/source write boundaries remain intact.

### 6. Complete Relevant Verification

After focused tests pass, run:

```bash
python3 -m pytest \
  tests/test_app_server_client.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_runless_runtime_contract.py \
  tests/test_runtime_broker.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- All selected tests pass.

### 7. Final Stale-path And Review Scan

Run:

```bash
rg -n '"turn/start"|turn/start|input_turn|--permissions|buddyswitch-runtime' tools/launcher tests docs/spec
```

Review every BuddySwitch-owned `turn/start` call site found by the scan.

Acceptance:

- No BuddySwitch idle input `turn/start` path omits `permissions: "buddyswitch-runtime"`.
- No `turn/start` request combines `permissions` with `sandboxPolicy`.
- No direct runtime object or buddybox write path was added.

## Review Acceptance Checklist

- The regression test would have caught the observed `Operation not permitted` class of failure.
- The test proves the launcher-level `instance input` path, not only a direct helper function.
- The test is requirement-driven: "new BuddySwitch turns keep runtime access."
- Active steering and non-steerable behavior are not weakened.
- No compatibility fallback or alternate old path is introduced.
