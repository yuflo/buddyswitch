# Codex App-server Service Mode Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace BuddySwitch TUI-first buddy instances with per-instance Codex app-server services and one clean service-mode CLI path.

**Architecture:** Add a small BuddySwitch-owned app-server lifecycle/client layer around Codex's native `codex app-server --listen unix://PATH`. The shell launcher keeps owning workspace, runtime broker, browser, and config setup. The Python app-server helper owns WebSocket-over-UDS JSON-RPC calls, health checks, thread start/resume, turn start/steer, interrupt, and shutdown marker cleanup.

**Tech Stack:** Bash launcher helpers, Python standard library only, Codex app-server JSON-RPC over WebSocket Unix socket, pytest/unittest launcher tests.

---

## Scope

This is one complete task. It can be implemented in stages, but the final delivered behavior must cover start, input, attach, stop, status/list, active guards, old path removal, tests, and verification.

Do not implement the later daemon or co-work message redesign in this plan.

## Files To Create

- `tools/launcher/app_server.sh`
  - shell wrapper functions sourced by `buddyswitch-codex`
  - computes app-server pid/socket/log paths
  - delegates lifecycle and RPC work to Python helper
  - exports instance env for service launch and attach

- `tools/launcher/app_server.py`
  - Python standard-library app-server lifecycle and JSON-RPC client
  - supports subcommands:
    - `status`
    - `ensure`
    - `stop`
    - `thread-start`
    - `thread-read`
    - `input`
    - `interrupt`
  - implements WebSocket-over-UDS client
  - writes app-server pid/socket marker files only
  - does not update `instance.json`; shell helpers own instance record mutations
  - writes no product runtime objects directly

- `tests/test_app_server_client.py`
  - unit tests for WebSocket-over-UDS JSON-RPC client and path helpers

## Files To Modify

- `buddyswitch-codex`
  - source `tools/launcher/app_server.sh`
  - replace TUI start lifecycle with app-server service lifecycle
  - add `instance input`, `instance attach`, `instance stop`, `instance status`, `instance interrupt`
  - remove `instance open` locked path
  - replace reset active check with app-server service check

- `tools/launcher/instance.sh`
  - update usage and command dispatch
  - remove `open`
  - reject `start --buddy <buddy> -- <codex args...>`
  - list service-mode fields

- `tools/launcher/env.sh`
  - keep `buddyswitch_run_codex`
  - remove or stop using launcher marker active helpers
  - add instance record update helpers for app-server fields

- `tools/launcher/cleanup.sh`
  - replace launcher marker counts with app-server service counts

- `tools/launcher/browser_cockpit.sh`
  - add explicit instance browser stop helper
  - keep existing ensure/status behavior

- `tools/launcher/codex_config.py`
  - no planned code change
  - tests must verify app-server startup still uses the same `buddyswitch-runtime` profile and broker socket allow-list

- `tests/test_buddyswitch_launcher.py`
  - replace TUI lifecycle tests with service-mode tests
  - add input/attach/stop/status/old-path-removal tests

- `tests/test_browser_cockpit_launcher.py`
  - add direct browser stop helper tests

- `tests/test_cleanup_system.py`
  - update cleanup active-service guard tests

- `tests/test_repo_consistency.py`
  - add guard ensuring launcher helpers do not write `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`

## Service Contract

### App-server Paths

Use one app-server socket per instance.

Default paths:

```text
<instance-root>/runtime/app-server.pid
<instance-root>/runtime/app-server.socket
<instance-root>/runtime/app-server.log
<instance-root>/runtime/app-server.sock
```

If the default socket path is too long for Unix sockets, use:

```text
/tmp/buddyswitch-app-server-<sha1(instance-id)[:12]>.sock
```

The marker file always stores the effective socket path.

### Process Launch

Launch app-server like this:

```bash
HOME="${BUDDYSWITCH_HOME}" \
CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
BUDDYSWITCH_ACTIVE_BUDDY="${buddy}" \
BUDDYSWITCH_INSTANCE_ID="${instance_id}" \
BUDDYSWITCH_INSTANCE_JSON="${BUDDYSWITCH_INSTANCE_JSON}" \
BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" \
codex app-server --listen "unix://${socket_path}"
```

Redirect stdout/stderr to `<instance-root>/runtime/app-server.log` unless app-server requires stdout for the selected transport. For Unix socket transport, log redirection is safe.

### App-server Client Handshake

Each client connection:

1. open Unix socket
2. send WebSocket HTTP Upgrade
3. send JSON-RPC `initialize`
4. read matching initialize response
5. send `initialized` notification
6. send exactly one or more JSON-RPC requests
7. ignore unrelated notifications while waiting for matching response ids

Use:

```json
{
  "clientInfo": {
    "name": "buddyswitch_launcher",
    "title": "BuddySwitch Launcher",
    "version": "0.1.0"
  },
  "capabilities": {
    "experimentalApi": true
  }
}
```

### Thread Creation

After app-server is ready, create a thread:

```json
{
  "method": "thread/start",
  "params": {
    "cwd": "<instance workspace dir>",
    "permissions": "buddyswitch-runtime",
    "runtimeWorkspaceRoots": [
      "<instance workspace dir>",
      "<shared project workspace dir>"
    ]
  }
}
```

Store `thread.id` in `instance.json`.

### Input Decision

`instance input` must query app-server before acting:

1. `thread/read` with `includeTurns=false`
2. if status is idle, call `turn/start`
3. if status is active:
   - call `thread/turns/list` with `limit=5`, `sortDirection="desc"`, `itemsView="summary"`
   - find the newest turn with `status == "inProgress"`
   - call `turn/steer` with that id as `expectedTurnId`
4. if no in-progress turn is found, return a clear unhealthy state instead of guessing

Text input payload:

```json
[
  {
    "type": "text",
    "text": "user text",
    "text_elements": []
  }
]
```

`--text` is required. Stdin input is not part of this task.

### Instance Record Ownership

Shell helpers own `instance.json` mutations. `tools/launcher/app_server.py` returns structured JSON for lifecycle and RPC results, and may create/remove only app-server runtime files:

- app-server pid file
- app-server socket marker
- app-server socket
- app-server log

`buddyswitch_instance_set_app_server` writes `thread_id`, `app_server_pid`, `app_server_socket`, and `app_server_log` after successful service start and thread creation.

`buddyswitch_instance_clear_app_server` clears `app_server_pid`, `app_server_socket`, and `app_server_log` during stop. It keeps `thread_id` as historical thread metadata unless the instance is deleted.

### Attach

`instance attach` launches a TUI remote client:

```bash
codex resume --remote "unix://${app_server_socket}" "${thread_id}"
```

It must run under the instance `HOME`, `CODEX_HOME`, `XDG_CONFIG_HOME`, and workspace cwd.

### Stop

`instance stop`:

1. sends `TERM` to the stored app-server pid when it is live
2. waits briefly
3. sends `KILL` if the pid is still live
4. removes app-server socket/pid/marker files
5. stops runtime broker
6. stops instance browser cockpit
7. marks instance inactive

Stop is idempotent for stale pids and stale sockets.

## Implementation Tasks

### Task 1: Add App-server Protocol Client Tests

**Files:**

- Create: `tests/test_app_server_client.py`

- [ ] Write tests for WebSocket-over-UDS handshake, initialize, initialized notification, JSON-RPC matching response, notification skipping, text input payload shape, server error handling, timeout, close frame, and long socket path fallback.

- [ ] Run:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected before implementation: tests fail because `tools/launcher/app_server.py` does not exist.

### Task 2: Implement Python App-server Client And Lifecycle Helper

**Files:**

- Create: `tools/launcher/app_server.py`

- [ ] Implement path helpers:
  - `default_socket_path(instance_root)`
  - `effective_socket_path(instance_id, instance_root, marker_file)`
  - `pid_file`, `marker_file`, `log_file`

- [ ] Implement minimal WebSocket client using only Python standard library:
  - UDS socket connect
  - HTTP Upgrade
  - masked client text frames
  - server text frames
  - close frame
  - ping/pong
  - response timeout

- [ ] Implement JSON-RPC client:
  - initialize
  - initialized notification
  - `request(method, params)`
  - matching by request id
  - structured errors

- [ ] Implement subcommands:
  - `status`
  - `ensure`
  - `stop`
  - `thread-start`
  - `thread-read`
  - `input`
  - `interrupt`

- [ ] Ensure helper never writes `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`.

- [ ] Run:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected after implementation: protocol client tests pass.

### Task 3: Add Shell App-server Lifecycle Wrapper

**Files:**

- Create: `tools/launcher/app_server.sh`
- Modify: `buddyswitch-codex`

- [ ] Source `tools/launcher/app_server.sh` from `buddyswitch-codex`.

- [ ] Add shell functions:
  - `buddyswitch_app_server_socket`
  - `buddyswitch_app_server_pid_file`
  - `buddyswitch_app_server_log_file`
  - `buddyswitch_app_server_is_active`
  - `buddyswitch_app_server_ensure`
  - `buddyswitch_app_server_stop`
  - `buddyswitch_app_server_input`
  - `buddyswitch_app_server_interrupt`

- [ ] Keep lifecycle locking in shell, matching runtime broker style.

- [ ] Run:

```bash
bash -n buddyswitch-codex tools/launcher/app_server.sh
python3 -m py_compile tools/launcher/app_server.py
```

Expected: both pass.

### Task 4: Replace Start With Service Startup

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add failing tests:
  - start starts app-server service and returns
  - start rejects Codex args passthrough
  - start browser failure stops broker and app-server is not launched
  - start stale app-server socket is cleaned

- [ ] Update usage:

```text
buddyswitch-codex instance start --buddy <buddy>
```

- [ ] Replace `start_codex` TUI execution with:
  - validate buddy
  - generate instance id
  - bind instance env
  - locked bootstrap
  - runtime broker ensure
  - config patch
  - browser bootstrap
  - app-server ensure
  - thread start
  - instance active update
  - print next commands

- [ ] Remove passthrough `--` handling from public start.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_starts_app_server_service_and_returns -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_codex_args_passthrough -q
```

Expected: new tests pass.

### Task 5: Implement Instance Input

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tools/launcher/app_server.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add failing tests for idle `turn/start`, active `turn/steer`, non-steerable active turn, inactive instance, unhealthy service, and missing `--text`.

- [ ] Add usage:

```text
buddyswitch-codex instance input <instance-id> --text <text>
```

- [ ] Reject missing `--text`. Do not add stdin input in this migration.

- [ ] Implement dynamic decision:
  - call app-server `thread/read`
  - if idle, `turn/start`
  - if active, `thread/turns/list` then `turn/steer`
  - if non-steerable, fail without fallback `turn/start`

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "input_" -q
```

Expected: input behavior tests pass.

### Task 6: Implement Attach

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add failing tests:
  - attach invokes remote resume
  - attach leaves service active
  - attach rejects missing thread id
  - attach rejects unhealthy app-server

- [ ] Add usage:

```text
buddyswitch-codex instance attach <instance-id>
```

- [ ] Implement attach with:

```bash
buddyswitch_run_codex resume --remote "unix://${socket_path}" "${thread_id}"
```

- [ ] Remove `instance open` from dispatch and help.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "attach or open_is_removed" -q
```

Expected: attach tests pass and old open test fails as removed when invoked.

### Task 7: Implement Stop And Browser Stop

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] Add browser helper:
  - `buddyswitch_browser_instance_stop <instance-id>`
  - kill pid from `<instance>/browser/chrome.pid` when live
  - remove stale pid marker
  - do not kill unrelated process when marker missing or invalid

- [ ] Add stop command:

```text
buddyswitch-codex instance stop <instance-id>
```

- [ ] Implement stop under runtime lock:
  - bind instance
  - stop app-server
  - stop runtime broker
  - stop browser cockpit
  - mark inactive

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "stop_" -q
python3 -m pytest tests/test_browser_cockpit_launcher.py -q
```

Expected: stop tests pass.

### Task 8: Implement Status, List Updates, And Interrupt

**Files:**

- Modify: `tools/launcher/instance.sh`
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/app_server.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add `instance status <instance-id> [--json]`.

- [ ] Update `instance list` columns to include:
  - instance id
  - buddy
  - status
  - app-server health
  - thread id
  - browser port
  - updated_at
  - workspace

- [ ] Add `instance interrupt <instance-id>`.

- [ ] Implement interrupt:
  - query active in-progress turn via `thread/turns/list`
  - call `turn/interrupt`
  - fail clearly if no active turn

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "status or list or interrupt" -q
```

Expected: status/list/interrupt tests pass.

### Task 9: Replace Active Guards

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] Add app-server active counting helpers:
  - all instances
  - by buddy
  - target instance

- [ ] Replace reset active check.

- [ ] Replace cleanup active check.

- [ ] Replace delete active check.

- [ ] Stop using launcher marker files as truth.

- [ ] Remove or isolate obsolete launcher marker helpers if no remaining tests require them.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "delete_blocks_active_app_server or reset_blocks_active_app_server or launcher_marker" -q
python3 -m pytest tests/test_cleanup_system.py -q
```

Expected: active guard tests pass.

### Task 10: Remove Old Public Path And Stale Tests

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Remove `__locked-instance-open-bootstrap` dispatch.

- [ ] Remove old `instance_open` functions.

- [ ] Replace tests named around `instance_open_*` with attach/start/status equivalents.

- [ ] Replace tests asserting stored instance becomes inactive after TUI exit. In service mode, start leaves it active until explicit stop.

- [ ] Update help tests to prove no old compatibility path remains.

- [ ] Run:

```bash
rg -n "instance open|__locked-instance-open|open existing|\\[-- codex args|launcher marker|count_active_launchers" buddyswitch-codex tools tests
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:

- `rg` returns only intentional historical text in docs, if any.
- launcher tests pass.

### Task 11: Repo Guardrails And Smoke Verification

**Files:**

- Modify: `tests/test_repo_consistency.py` if guard does not already exist
- Optionally modify docs if user-facing help needs a durable note

- [ ] Add or confirm guardrail test that new launcher helpers do not write product runtime object/buddybox paths directly.

- [ ] Run focused verification:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_browser_cockpit_launcher.py -q
python3 -m pytest tests/test_cleanup_system.py -q
python3 -m pytest tests/test_clean_runtime_environment.py tests/test_repo_consistency.py -q
```

- [ ] Run optional real smoke if local Codex/auth allow it:

```bash
BUDDYSWITCH_REAL_CODEX_APP_SERVER_SMOKE=1 python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_real_codex_app_server_start_input_status_stop_smoke -q
```

Expected: focused automated verification passes. If real smoke is skipped, report why.

## Implementation Order

Use this order to avoid half-migration ambiguity:

1. Protocol client tests and helper.
2. Service start.
3. Input.
4. Attach.
5. Stop.
6. Status/list/interrupt.
7. Active guard replacement.
8. Old path removal.
9. Full verification.

Do not merge or call the task done while old TUI start/open behavior still exists as a working public path.

## Risk Controls

- WebSocket-over-UDS is the riskiest new code. Keep it small and fully unit-tested.
- Do not store active turn id as truth. Always query app-server.
- Stop must be idempotent. Stale service state is expected during development.
- Keep runtime broker lifecycle code intact except where app-server status replaces launcher-marker active checks.
- Keep Codex config patching centralized in `codex_config.py`.
- Keep browser ownership explicit. If BuddySwitch starts it for the instance, BuddySwitch stop should stop it.
