# Launcher Side Conversations Test Plan

Date: 2026-05-25

## Test Goal

Prove BuddySwitch launcher supports Codex-style side conversations as explicit child-thread operations without mixing them into the main instance thread.

The tests must start from product behavior: a side conversation is created from a parent instance thread, receives its own child thread id, can be continued by that side thread id, and can be closed without interrupting the parent. Tests must not pass by merely checking that a particular helper function was called; they must prove the app-server JSON-RPC contract and launcher state boundary.

## Current Code Findings

- `buddyswitch-codex instance input <id> --text` reads the instance `thread_id` and sends text to that main thread through `buddyswitch_app_server_input`.
- `tools/launcher/app_server.py::input_turn` already implements the low-level "send text to a thread" behavior: idle threads use `turn/start`; active threads use `turn/steer`.
- `buddyswitch-codex instance interrupt <id>` reads the same main `thread_id` and calls `turn/interrupt`; it is not suitable for closing a side child thread.
- `tools/launcher/web_management.py` exposes `/api/instances/<id>/input` and `/interrupt` by delegating to the CLI command layer, but has no side routes.
- `tests/helpers/fake_codex.py` currently stores one flat thread state. Side conversation tests need fake app-server support for multiple thread ids so tests can prove parent and child are independent.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `instance side <id> --text <text>` creates a new child thread from the instance main `thread_id`. |
| FR2 | New side creation calls Codex app-server `thread/fork` with the parent `threadId`, `ephemeral: true`, BuddySwitch runtime workspace roots, and `permissions: "buddyswitch-runtime"`. |
| FR3 | New side creation injects a side boundary prompt into the child with `thread/inject_items` before sending user text. |
| FR4 | New side creation sends the user text to the child thread, not to the parent thread. |
| FR5 | New side creation returns `side_thread_id`; JSON may include `turn_id`, but users do not need to pass `turn_id` later. |
| FR6 | `instance side <id> --side-thread-id <side> --text <text>` continues a registered side child thread and does not fork a new child. |
| FR7 | Continuing a side child uses the same low-level thread send behavior as main input: idle side threads use `turn/start`; active side threads use `turn/steer`. |
| FR8 | Side send rejects an unknown `side_thread_id` before any mutating app-server call. |
| FR9 | Side send rejects the parent main `thread_id` when it is supplied as `--side-thread-id`. |
| FR10 | `instance side close <id> --side-thread-id <side>` closes only the registered child thread. |
| FR11 | Side close interrupts an active child turn with that child `turnId`; it never calls `turn/interrupt` on the parent thread. |
| FR12 | Side close also succeeds for an idle registered child by sending Codex startup interrupt payload `turnId: ""`, matching TUI side cleanup semantics. |
| FR13 | Side close removes the child from BuddySwitch side registry state. |
| FR14 | Main `instance interrupt` behavior remains unchanged and continues to target only the main instance `thread_id`. |
| FR15 | Web management API exposes the same create, send, and close capabilities without requiring frontend UI changes. |
| FR16 | Inactive, unhealthy, missing-thread, missing-text, and unknown-side cases fail before side app-server mutations. |
| FR17 | No runtime product object files under `buddyswitch/objects/**` or old buddybox runtime paths are written directly. Side registry lives in launcher instance metadata only. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | CLI side-create integration test captures `thread/fork` and child id in JSON output. |
| FR2 | Same test asserts `thread/fork` params: parent `threadId`, `ephemeral`, `permissions`, and `runtimeWorkspaceRoots`. |
| FR3 | Same test asserts `thread/inject_items` params and boundary prompt fragments. |
| FR4 | Same test asserts `turn/start.threadId == side_thread_id` and no `turn/start` targets parent. |
| FR5 | CLI JSON and human-output tests assert `side_thread_id` is present. |
| FR6 | CLI side-send test asserts no second `thread/fork` appears. |
| FR7 | CLI side-send tests cover idle `turn/start` and active `turn/steer` on side thread. |
| FR8 | CLI unknown side test asserts non-zero exit and no `turn/start`, `turn/steer`, or `turn/interrupt`. |
| FR9 | CLI main-thread-as-side test asserts non-zero exit and no parent mutation. |
| FR10 | CLI side-close test asserts close command succeeds for a registered child. |
| FR11 | Active close test asserts `turn/interrupt.threadId == side_thread_id`. |
| FR12 | Idle close test asserts `turn/interrupt.turnId == ""`. |
| FR13 | Close test reads `instance.json` and asserts the child was removed from `side_threads`. |
| FR14 | Existing `test_interrupt_interrupts_active_turn` and JSON interrupt tests remain in focused verification. |
| FR15 | Web management tests assert side routes delegate to the CLI side commands and parse payloads. |
| FR16 | CLI and web validation tests assert failure before mutating JSON-RPC calls. |
| FR17 | Existing repo/runtime boundary tests remain in broad verification. |

## Test Data And Fakes

Use `tests/helpers/fake_codex.py` as the Codex app-server boundary fake. This is the right boundary because BuddySwitch owns launcher behavior and app-server protocol calls, not model behavior.

Upgrade the fake to support multiple thread ids while preserving existing flat-state tests:

```json
{
  "thread_id": "thread-main",
  "thread_status": {"type": "idle"},
  "turns": [],
  "next_side_thread_id": "thread-side-1",
  "threads": {
    "thread-main": {
      "status": {"type": "idle"},
      "turns": []
    },
    "thread-side-1": {
      "status": {"type": "active", "activeFlags": []},
      "turns": [
        {"id": "turn-side-1", "status": "inProgress"}
      ],
      "injected_items": []
    }
  }
}
```

Compatibility rule:

- If `threads` is absent, the fake must synthesize the main thread entry from legacy `thread_status` and `turns`.
- When mutating the main thread, the fake must mirror status and turns back to the legacy flat keys so existing tests keep their current assertions.

The fake must implement these app-server methods for side tests:

- `thread/fork`
- `thread/inject_items`
- `thread/read`
- `thread/turns/list`
- `turn/start`
- `turn/steer`
- `turn/interrupt`

## Detailed Test Cases

### 1. App-server Helper Side Payload Shape

Modify:

- `tests/test_app_server_client.py`

Add:

- `test_side_boundary_prompt_item_shape_is_codex_compatible`

Assertions:

```python
item = APP_SERVER.side_boundary_prompt_item()
self.assertEqual(item["type"], "message")
self.assertEqual(item["role"], "user")
content = item["content"]
self.assertEqual(len(content), 1)
self.assertEqual(content[0]["type"], "input_text")
self.assertIn("Side conversation boundary.", content[0]["text"])
self.assertIn("inherited history", content[0]["text"])
self.assertIn("separate from the main thread", content[0]["text"])
```

Add:

- `test_side_commands_require_expected_arguments`

Assertions:

```python
parser = APP_SERVER.build_parser()
with self.assertRaises(SystemExit):
    parser.parse_args(["side-start", "--socket", "/tmp/app.sock", "--parent-thread-id", "thread-main"])

args = parser.parse_args([
    "side-start",
    "--socket", "/tmp/app.sock",
    "--parent-thread-id", "thread-main",
    "--text", "Check this",
    "--workspace-dir", "/tmp/workspace",
    "--shared-project-workspace-dir", "/tmp/project",
    "--permissions", "buddyswitch-runtime",
])
self.assertEqual(args.parent_thread_id, "thread-main")
self.assertEqual(args.permissions, "buddyswitch-runtime")

close_args = parser.parse_args([
    "side-close",
    "--socket", "/tmp/app.sock",
    "--side-thread-id", "thread-side-1",
])
self.assertEqual(close_args.side_thread_id, "thread-side-1")
```

Focused command:

```bash
python3 -m pytest tests/test_app_server_client.py -k "side_boundary or side_commands" -q
```

Expected before implementation:

```text
FAILED
```

### 2. CLI Creates Side Child, Injects Boundary, Sends Text To Child

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_creates_child_injects_boundary_and_sends_text`

Setup:

- Start service instance with fake app-server.
- Clear the calls file after `instance start`.
- Run:

```bash
./buddyswitch-codex instance side <instance-id> --text "Explore the API shape" --json
```

Assertions:

```python
payload = json.loads(side_result.stdout)
self.assertEqual(payload["instance_id"], ctx["instance_id"])
self.assertEqual(payload["parent_thread_id"], ctx["instance_payload"]["thread_id"])
self.assertEqual(payload["side_thread_id"], "thread-side-1")
self.assertEqual(payload["action"], "start")
self.assertTrue(payload.get("turn_id"))
```

Captured JSON-RPC assertions:

```python
methods = [row["rpc_method"] for row in rpc_rows]
self.assertIn("thread/fork", methods)
self.assertIn("thread/inject_items", methods)
self.assertIn("turn/start", methods)

fork = next(row for row in rpc_rows if row["rpc_method"] == "thread/fork")
self.assertEqual(fork["params"]["threadId"], ctx["instance_payload"]["thread_id"])
self.assertTrue(fork["params"]["ephemeral"])
self.assertEqual(fork["params"]["permissions"], "buddyswitch-runtime")
self.assertIn("runtimeWorkspaceRoots", fork["params"])
self.assertIn("developerInstructions", fork["params"])
self.assertIn("side conversation", fork["params"]["developerInstructions"])

inject = next(row for row in rpc_rows if row["rpc_method"] == "thread/inject_items")
self.assertEqual(inject["params"]["threadId"], "thread-side-1")
item = inject["params"]["items"][0]
self.assertEqual(item["type"], "message")
self.assertEqual(item["role"], "user")
self.assertIn("Side conversation boundary.", item["content"][0]["text"])

turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
self.assertEqual(turn_start["params"]["threadId"], "thread-side-1")
self.assertEqual(
    turn_start["params"]["input"],
    [{"type": "text", "text": "Explore the API shape", "text_elements": []}],
)
self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
self.assertNotEqual(turn_start["params"]["threadId"], ctx["instance_payload"]["thread_id"])
```

Registry assertion:

```python
instance_payload = json.loads((ctx["instance_root"] / "instance.json").read_text(encoding="utf-8"))
self.assertEqual(
    instance_payload["side_threads"],
    [
        {
            "thread_id": "thread-side-1",
            "parent_thread_id": ctx["instance_payload"]["thread_id"],
            "status": "open",
        }
    ],
)
```

The real implementation may include timestamps in the registry objects; in that case assert the required fields instead of exact object equality.

Focused command:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_side_creates_child_injects_boundary_and_sends_text -q
```

Expected before implementation:

```text
FAILED
```

### 3. CLI Human Output Returns Side Thread Id

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_create_human_output_prints_side_thread_id`

Run:

```bash
./buddyswitch-codex instance side <instance-id> --text "Explore the API shape"
```

Assertions:

```python
self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
self.assertIn("Side conversation started:", side_result.stdout)
self.assertIn("thread-side-1", side_result.stdout)
self.assertNotIn("{", side_result.stdout)
```

### 4. CLI Continues Registered Active Side With Steer

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_send_existing_active_child_steers_side_not_parent`

Setup:

- Create a side first, or seed `instance.json` with a `side_threads` entry whose `parent_thread_id` is the main thread.
- Seed fake state so `thread-side-1` is active with in-progress turn `turn-side-1`.

Run:

```bash
./buddyswitch-codex instance side <instance-id> --side-thread-id thread-side-1 --text "Narrow that answer" --json
```

Assertions:

```python
payload = json.loads(side_result.stdout)
self.assertEqual(payload["action"], "send")
self.assertEqual(payload["side_thread_id"], "thread-side-1")
self.assertEqual(payload["parent_thread_id"], ctx["instance_payload"]["thread_id"])
self.assertEqual(payload["thread_action"], "steer")
self.assertEqual(payload["expected_turn_id"], "turn-side-1")

methods = [row["rpc_method"] for row in rpc_rows]
self.assertNotIn("thread/fork", methods)
self.assertIn("turn/steer", methods)
steer = next(row for row in rpc_rows if row["rpc_method"] == "turn/steer")
self.assertEqual(steer["params"]["threadId"], "thread-side-1")
self.assertEqual(steer["params"]["expectedTurnId"], "turn-side-1")
self.assertNotEqual(steer["params"]["threadId"], ctx["instance_payload"]["thread_id"])
```

### 5. CLI Continues Registered Idle Side With New Turn

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_send_existing_idle_child_starts_side_turn`

Setup:

- Registered `thread-side-1`.
- Fake state has `thread-side-1` status idle and no in-progress turns.

Run:

```bash
./buddyswitch-codex instance side <instance-id> --side-thread-id thread-side-1 --text "Follow up" --json
```

Assertions:

```python
payload = json.loads(side_result.stdout)
self.assertEqual(payload["action"], "send")
self.assertEqual(payload["thread_action"], "start")

turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
self.assertEqual(turn_start["params"]["threadId"], "thread-side-1")
self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
```

### 6. CLI Rejects Unknown Side Thread Before Mutating Calls

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_send_rejects_unknown_side_thread_without_rpc_mutation`

Run:

```bash
./buddyswitch-codex instance side <instance-id> --side-thread-id thread-unknown --text "Do not send"
```

Assertions:

```python
self.assertNotEqual(side_result.returncode, 0)
self.assertIn("not registered", side_result.stderr.lower())
methods = [row["rpc_method"] for row in rpc_rows]
self.assertNotIn("thread/fork", methods)
self.assertNotIn("turn/start", methods)
self.assertNotIn("turn/steer", methods)
self.assertNotIn("turn/interrupt", methods)
```

### 7. CLI Rejects Main Thread As Side Thread

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_send_rejects_main_thread_id_as_side_thread`
- `test_side_close_rejects_main_thread_id_as_side_thread`

Run:

```bash
./buddyswitch-codex instance side <instance-id> --side-thread-id <main-thread-id> --text "Bad"
./buddyswitch-codex instance side close <instance-id> --side-thread-id <main-thread-id>
```

Assertions:

```python
self.assertNotEqual(result.returncode, 0)
self.assertIn("main thread", result.stderr.lower())
self.assertNotIn("turn/interrupt", methods)
self.assertNotIn("turn/start", methods)
self.assertNotIn("turn/steer", methods)
```

### 8. CLI Closes Active Registered Side Only

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_close_interrupts_registered_child_and_removes_registry`

Setup:

- Registered `thread-side-1`.
- Fake state has `thread-side-1` active with turn `turn-side-1`.

Run:

```bash
./buddyswitch-codex instance side close <instance-id> --side-thread-id thread-side-1 --json
```

Assertions:

```python
payload = json.loads(close_result.stdout)
self.assertEqual(payload["action"], "close")
self.assertEqual(payload["side_thread_id"], "thread-side-1")
self.assertEqual(payload["parent_thread_id"], ctx["instance_payload"]["thread_id"])
self.assertEqual(payload["turn_id"], "turn-side-1")

interrupt = next(row for row in rpc_rows if row["rpc_method"] == "turn/interrupt")
self.assertEqual(interrupt["params"]["threadId"], "thread-side-1")
self.assertEqual(interrupt["params"]["turnId"], "turn-side-1")

instance_payload = json.loads((ctx["instance_root"] / "instance.json").read_text(encoding="utf-8"))
self.assertEqual(instance_payload.get("side_threads", []), [])
```

Also assert the parent thread remains not interrupted in fake state.

### 9. CLI Closes Idle Registered Side With Startup Interrupt

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_close_idle_registered_child_uses_startup_interrupt`

Setup:

- Registered `thread-side-1`.
- Fake state has `thread-side-1` idle and no in-progress turns.

Run:

```bash
./buddyswitch-codex instance side close <instance-id> --side-thread-id thread-side-1 --json
```

Assertions:

```python
interrupt = next(row for row in rpc_rows if row["rpc_method"] == "turn/interrupt")
self.assertEqual(interrupt["params"]["threadId"], "thread-side-1")
self.assertEqual(interrupt["params"]["turnId"], "")
self.assertTrue(payload["startup_interrupt"])
```

### 10. CLI Validation Failures

Modify:

- `tests/test_buddyswitch_launcher.py`

Add:

- `test_side_create_requires_text`
- `test_side_send_requires_text`
- `test_side_close_requires_side_thread_id`
- `test_side_rejects_inactive_or_unhealthy_instance`

Assertions:

- Missing text returns `2`.
- Missing `--side-thread-id` for close returns `2`.
- Inactive or unhealthy instance returns `3`.
- No side mutating JSON-RPC methods are captured.

### 11. Main Interrupt Remains Main Only

Modify:

- Existing tests in `tests/test_buddyswitch_launcher.py`.

Focused command:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_interrupt_interrupts_active_turn \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_interrupt_json_returns_interrupted_turn \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_interrupt_rejects_when_no_active_turn_exists \
  -q
```

Expected:

- Still passes.
- `instance interrupt` does not read or use `side_threads`.

### 12. Web API Side Routes

Modify:

- `tests/test_web_management.py`

Add:

- `test_side_create_route_delegates_and_reports_side_thread_id`
- `test_side_send_route_delegates_existing_side`
- `test_side_close_route_delegates_and_reports_side_thread_id`
- `test_side_route_rejects_empty_text`
- `test_side_close_route_rejects_missing_side_thread_id`

Expected CLI delegations:

```python
["instance", "side", "inst-pm-demo", "--text", "Explore", "--json"]
["instance", "side", "inst-pm-demo", "--side-thread-id", "thread-side-1", "--text", "Follow up", "--json"]
["instance", "side", "close", "inst-pm-demo", "--side-thread-id", "thread-side-1", "--json"]
```

Expected API payload shape:

```json
{
  "ok": true,
  "action": "start",
  "side_thread_id": "thread-side-1",
  "parent_thread_id": "thread-main",
  "turn_id": "turn-side-1",
  "instance": {}
}
```

For send:

```json
{
  "ok": true,
  "action": "send",
  "thread_action": "steer",
  "side_thread_id": "thread-side-1",
  "parent_thread_id": "thread-main",
  "expected_turn_id": "turn-side-1",
  "instance": {}
}
```

For close:

```json
{
  "ok": true,
  "action": "close",
  "side_thread_id": "thread-side-1",
  "parent_thread_id": "thread-main",
  "turn_id": "turn-side-1",
  "instance": {}
}
```

Focused command:

```bash
python3 -m pytest tests/test_web_management.py -k "side" -q
```

## Verification Commands

Focused verification after implementation:

```bash
python3 -m pytest tests/test_app_server_client.py -k "side" -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k "side or interrupt" -q
python3 -m pytest tests/test_web_management.py -k "side" -q
```

Broader launcher verification:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py tests/test_web_management.py -q
```

Boundary verification:

```bash
python3 -m pytest tests/test_clean_runtime_environment.py tests/test_repo_consistency.py -q
```

## Self Review

- Functional coverage: FR1 through FR17 each map to at least one test case.
- Product boundary: tests prove side child operations target child thread ids and reject main thread ids.
- No transition workaround: no test accepts sending `/side ...` through `instance input`.
- State boundary: tests require side registry in launcher instance metadata and do not use product runtime object files.
- Residual risk: these tests fake Codex model execution. They verify BuddySwitch's app-server protocol contract, not real model answers.
