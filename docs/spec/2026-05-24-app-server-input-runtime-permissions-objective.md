# App-server Input Runtime Permissions Objective

Date: 2026-05-24

## Goal

Fix BuddySwitch app-server input turns so every new turn created through:

```bash
./buddyswitch-codex instance input <instance-id> --text "<work>"
```

keeps the same `buddyswitch-runtime` permission profile that BuddySwitch selected when the instance thread was created.

This is a forward repair. There must be one clear runtime path:

1. `instance start` creates a managed app-server thread with the BuddySwitch runtime permission profile.
2. `instance input` starts a new turn or steers an active turn through the same app-server service.
3. Any new turn started by BuddySwitch remains able to reach the runtime broker and env tools.

## Current Bottleneck

BuddySwitch service-mode instances are reachable through app-server, but later `instance input` turns can lose the runtime permission profile. When that happens, the buddy cannot connect to the runtime broker Unix socket and falls back to direct text responses instead of using the durable runtime tool path.

Observed failure shape:

```text
runtime-broker.sock: [Errno 1] Operation not permitted
```

This is not a broker availability failure. The broker can be healthy and reachable from a correctly configured outer shell while the Codex turn itself is running under a restrictive permission profile.

## Code Review Facts Confirmed

Checked in this worktree.

### BuddySwitch Code

- `tools/launcher/app_server.py`
  - `thread_start(...)` sends `thread/start` with:
    - `cwd`
    - `permissions`
    - `runtimeWorkspaceRoots`
  - `input_turn(...)` sends idle `turn/start` with:
    - `threadId`
    - `input`
  - `input_turn(...)` does not send `permissions` on the idle new-turn path.
- `tools/launcher/app_server.sh`
  - `buddyswitch_app_server_thread_start` passes `--permissions "buddyswitch-runtime"`.
  - `buddyswitch_app_server_input` does not pass a permission profile to the Python helper.
- `tests/test_buddyswitch_launcher.py`
  - `test_input_starts_turn_when_thread_idle` proves `turn/start` is called and the text input shape is correct.
  - It does not assert that `turn/start.params.permissions == "buddyswitch-runtime"`.

### Codex App-server Protocol Facts

Checked against local Codex source under `/Users/chen/Dev/codex`.

- `TurnStartParams` includes an optional `permissions` field.
- The protocol comment states that `turn/start.permissions` selects a named permission profile id for this turn and subsequent turns.
- `permissions` cannot be combined with `sandboxPolicy`.
- The app-server turn processor reads `params.permissions`, loads the selected profile, and applies it to the turn settings.

## Root Cause

BuddySwitch passes `buddyswitch-runtime` only during `thread/start`, then omits it on later idle `turn/start` calls issued by `instance input`.

Codex app-server treats `turn/start.permissions` as the explicit per-turn permission profile selection. Without that field, later input-created turns can run with a restrictive default such as read-only. In that state the runtime broker socket connection is denied, so context/tool/durable write paths fail before taskbox or artifact behavior can operate.

## Why Earlier Tests Missed This

The previous app-server service-mode test plan covered service lifecycle and app-server RPC shape, but did not encode the product invariant that every BuddySwitch-created turn must retain runtime broker access.

Specific omissions:

1. Start tests checked generated config and app-server launch, but did not fully protect permission propagation across later `instance input` turns.
2. Input tests checked `turn/start` versus `turn/steer` and text payload shape, but not `turn/start.params.permissions`.
3. Smoke coverage used benign text prompts and did not force an env tool or runtime broker access path.
4. No test inspected the JSON-RPC payload for a second input-created idle turn to ensure it kept `buddyswitch-runtime`.
5. No acceptance criterion stated that app-server input turns must not degrade to read-only.

## Forward Decisions

1. `buddyswitch-runtime` remains the single BuddySwitch runtime permission profile.
2. BuddySwitch must explicitly send that profile when it starts an idle `turn/start` through `instance input`.
3. The fix must not add a fallback to legacy TUI behavior.
4. The fix must not add broker bypasses, direct file writes, mirror state, or migration compatibility.
5. The fix must not change taskbox, message, buddybox, artifact, or track product semantics.
6. The fix must not introduce a generic permission framework.
7. The fix must not modify Codex source.

## Non-goals

- Do not redesign app-server lifecycle.
- Do not change `instance attach` behavior except to verify it is not the source of this bug.
- Do not change runtime broker protocol.
- Do not change task storage or task skill semantics.
- Do not create a separate permission profile.
- Do not make `instance input` silently recover by direct runtime file access.
- Do not preserve a no-permissions input path for compatibility.

## Target Behavior

### Idle Thread

When `instance input` finds the thread idle, it calls:

```json
{
  "method": "turn/start",
  "params": {
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
}
```

The request must not include `sandboxPolicy` together with `permissions`.

### Active Thread

When `instance input` finds an active steerable turn, it keeps the existing `turn/steer` path:

```json
{
  "method": "turn/steer",
  "params": {
    "threadId": "<thread-id>",
    "expectedTurnId": "<active-turn-id>",
    "input": [
      {
        "type": "text",
        "text": "<user text>",
        "text_elements": []
      }
    ]
  }
}
```

No duplicate `turn/start` is allowed while a turn is active.

### Runtime Broker Access

After a new input-created turn starts, the buddy must be able to use the runtime broker and env tools under normal BuddySwitch runtime rules. The launcher must continue to generate Codex config that includes:

- `default_permissions = "buddyswitch-runtime"`
- `permissions.buddyswitch-runtime`
- the runtime broker Unix socket allow-list entry

## Success Criteria

The task is complete only when:

1. A regression test fails before the fix because idle `instance input` sends `turn/start` without `permissions`.
2. The implementation makes idle input-created `turn/start` include `permissions: "buddyswitch-runtime"`.
3. `turn/start` does not include a conflicting `sandboxPolicy`.
4. Existing active-turn steering behavior remains unchanged and covered.
5. Existing service-mode start, attach, stop, and runtime config tests still pass.
6. Focused and broader relevant tests pass.
7. A final review finds no remaining no-permission `turn/start` path in BuddySwitch launcher code.
