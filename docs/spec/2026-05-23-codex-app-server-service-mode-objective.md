# Codex App-server Service Mode Objective

Date: 2026-05-23

## Goal

Replace BuddySwitch's TUI-first buddy lifecycle with one long-running Codex app-server service per buddy instance.

This is a forward replacement. The first implementation must leave one clear path:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance input inst-pm-xxx --text "Advance the PM brief"
./buddyswitch-codex instance attach inst-pm-xxx
./buddyswitch-codex instance stop inst-pm-xxx
```

`start` starts the service. `input` sends work. `attach` opens a human TUI connected to the running service. `stop` ends the service lifecycle.

## Current Bottleneck

BuddySwitch currently treats a buddy as a `codex` TUI process. That blocks co-work because an external coordinator has no stable control channel while the buddy is busy inside a turn.

The immediate product improvement is to make each buddy controllable through Codex app-server APIs while preserving the existing BuddySwitch runtime boundaries:

- buddy identity
- per-instance `HOME`
- per-instance `CODEX_HOME`
- per-instance workspace
- runtime broker
- browser cockpit
- launcher-managed Codex config
- env tools for durable runtime writes

The later daemon and message upgrade depends on this control channel, but is not part of this task.

## Forward Decisions

1. `instance start --buddy <buddy>` starts a long-running app-server. It does not enter TUI.
2. `instance input <instance-id> --text <text>` is the only user-facing send command. Internally it chooses `turn/start` or `turn/steer`.
3. `instance attach <instance-id>` replaces `instance open <instance-id>`.
4. `instance stop <instance-id>` owns service shutdown and marks the instance inactive.
5. Active state is defined by app-server health, not by a launcher/TUI pid marker.
6. Runtime broker and browser cockpit lifecycles follow the app-server service lifecycle, not the attach/TUI lifecycle.
7. No shared co-work task/task-list is introduced. Existing track, artifact, comment, message, and later message improvements remain the co-work substrate. Task remains buddy-private self-management.

## Non-goals

- Do not implement the co-work daemon in this task.
- Do not redesign the message system in this task.
- Do not introduce shared co-work tasks.
- Do not modify Codex source.
- Do not run multiple control paths in parallel for old and new behavior.
- Do not preserve `instance open` as a compatibility alias.
- Do not preserve `instance start --buddy <buddy> -- <codex args...>` passthrough.
- Do not expose separate user commands named `send` and `steer`.
- Do not use `codex app-server daemon`; BuddySwitch should own per-instance lifecycle.
- Do not treat `codex app-server proxy` as JSONL. It only proxies raw bytes for the WebSocket-over-UDS stream.

## Codex Source Facts Confirmed

Checked against `/Users/chen/Dev/codex` and local `codex` help.

- `codex app-server --listen` supports `stdio://`, `unix://`, `unix://PATH`, `ws://IP:PORT`, and `off`.
- Unix socket transport is WebSocket over Unix socket with an HTTP Upgrade handshake.
- `codex app-server proxy` proxies raw bytes; it does not convert the protocol to JSONL.
- `thread/start`, `thread/resume`, `thread/read`, `thread/turns/list`, `turn/start`, `turn/steer`, and `turn/interrupt` are app-server methods.
- `turn/steer` requires `expectedTurnId`.
- `turn/start` and `turn/steer` accept `input: [{"type":"text","text":"...","text_elements":[]}]`.
- `thread/status` can be active or idle, but the active turn id must be read from recent turns, not guessed from stale local state.
- `codex resume --remote unix://PATH <SESSION_ID>` is supported and is the right base for `instance attach`.
- Slash commands are TUI-side parsing. App-server clients must call structured methods instead of sending `/goal`, `/compact`, or similar slash text.

## BuddySwitch Source Facts Confirmed

Checked in this worktree.

- `buddyswitch-codex` currently runs `buddyswitch_run_codex "$@"` from `start_codex` and `instance_open`.
- `start` and `open` currently mark the instance inactive after the TUI exits.
- `tools/launcher/env.sh` currently has launcher marker helpers such as `buddyswitch_write_launcher_marker` and `buddyswitch_count_active_launchers`.
- `tools/launcher/instance.sh` currently routes `open` to TUI startup.
- `delete`, `reset`, and `cleanup` currently block on launcher markers.
- `runtime_broker.sh` already has a good lifecycle shape: `status`, `ensure`, `stop`, pid file, socket marker, log file.
- `browser_cockpit.sh` can start and detect browser cockpit, but has no stop command yet.
- `codex_config.py` already patches the per-instance `CODEX_HOME/config.toml`, including `buddyswitch-runtime` permissions and runtime broker Unix socket allow-list.

## Target User Experience

### Start

```bash
./buddyswitch-codex instance start --buddy pm
```

Expected behavior:

- create a new instance id
- prepare workspace and project worktree
- install runtime agents, skills, excludes, hooks
- start runtime broker
- patch Codex config
- ensure browser cockpit when required by the buddy profile
- start `codex app-server --listen unix://<socket>`
- create one app-server thread for the instance
- write `thread_id`, app-server pid, socket, log path, browser port, and active status to `instance.json`
- return immediately with next commands

### Input

```bash
./buddyswitch-codex instance input inst-pm-xxx --text "Advance the landing page PM brief"
```

Expected behavior:

- verify the instance exists and the app-server is healthy
- read the thread status and recent turns
- if idle, call `turn/start`
- if active and the active turn is steerable, call `turn/steer` with `expectedTurnId`
- if active but not steerable, fail with a clear message instead of creating a duplicate turn
- update only diagnostic fields such as last turn id/status after the API call succeeds

### Attach

```bash
./buddyswitch-codex instance attach inst-pm-xxx
```

Expected behavior:

- verify the instance exists and app-server is healthy
- launch:

```bash
codex resume --remote unix://<socket> <thread_id>
```

- use the instance `HOME`, `CODEX_HOME`, and `XDG_CONFIG_HOME`
- attach exit does not stop the service and does not mark the instance inactive

### Stop

```bash
./buddyswitch-codex instance stop inst-pm-xxx
```

Expected behavior:

- stop the app-server process
- remove app-server socket, pid marker, and transient socket marker
- stop runtime broker
- stop instance browser cockpit if BuddySwitch started it
- mark the instance inactive

### Status And List

```bash
./buddyswitch-codex instance status inst-pm-xxx
./buddyswitch-codex instance list
```

Expected behavior:

- show app-server health, thread id, thread status, browser port, workspace, and updated time
- inactive means no healthy app-server service
- stale pid or stale socket is reported as unhealthy; markers are removed only when the stored pid is not live

## Data Shape

`instance.json` remains the authoritative instance record. Add only concrete fields needed for service mode:

```json
{
  "instance_id": "inst-pm-20260523-abc123",
  "buddy": "pm",
  "status": "active",
  "workspace_dir": ".../instances/inst-pm-xxx/workspace",
  "browser_port": 9222,
  "thread_id": "uuid-or-thread-id",
  "app_server_pid": 12345,
  "app_server_socket": ".../runtime/app-server.sock",
  "app_server_log": ".../runtime/app-server.log",
  "updated_at": "2026-05-23T00:00:00Z"
}
```

Do not store active turn state as truth. It can be recorded as diagnostics only after API calls, but `input` and `interrupt` must query app-server before acting.

Runtime files:

- `<instance>/runtime/app-server.pid`
- `<instance>/runtime/app-server.socket`
- `<instance>/runtime/app-server.log`
- `<instance>/runtime/app-server.sock` when the path is short enough
- `/tmp/buddyswitch-app-server-<hash>.sock` when the instance path is too long for a Unix socket

## Code Cleanup Required

The implementation must remove the old main path instead of preserving it:

- remove `instance open` from help and dispatch
- remove `instance start --buddy <buddy> [-- codex args...]` from help and behavior
- replace `start_codex` TUI launch logic with service startup logic
- remove `instance_open` and `instance_open_locked_bootstrap`
- remove launcher marker active checks from instance lifecycle, reset, and cleanup
- replace launcher marker tests with app-server service health tests
- keep `buddyswitch_run_codex` only for app-server process launch, `mcp add/remove`, and remote TUI attach where needed

## Success Criteria

The task is complete only when:

1. Start/input/attach/stop work through app-server service mode.
2. Old `open` and TUI passthrough start paths are removed.
3. Active detection uses app-server health.
4. Runtime broker and browser lifecycle match service lifecycle.
5. Delete/reset/cleanup block on active services, not launcher markers.
6. Tests prove the behavior from functional requirements, not from implementation internals.
7. A focused verification run and a main-path smoke run pass.
