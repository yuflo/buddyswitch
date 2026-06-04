# Needs Parent Broker Source Root Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Use `superpowers:test-driven-development`: write the focused regression first,
> confirm it fails with the current bug, implement the smallest direct fix, then rerun the focused
> and broader checks.

**Goal:** Make `message.mark(needs_parent)` parent handoff work from projected runtime workspaces,
including the real stdio MCP -> runtime broker path used by live actor side threads.

**Architecture:** Treat source repo root and runtime workspace root as separate facts. The runtime
broker may execute from the projected workspace and load the projected manifest, but parent handoff
must import launcher code from the source checkout root that contains `tools/launcher/daemon_core.py`.
Do not change message disposition semantics, task checkout, request, or track behavior in this fix.

**Tech Stack:** Python runtime broker, launcher shell glue, env.tool message implementation, JSON
runtime state, unittest/pytest, and lightweight subprocess broker coverage.

---

## Current Verified Failure

This bug was reproduced with `act-market-83d8c91e5a82` receiving `msg-5893131f4e5f` from
`act-market-84276b976354`.

Observed facts:

- The incoming message changed the parent thread's active research priority.
- The receiver side thread read the message and twice called:
  `message__mark` with `message_id="msg-5893131f4e5f"`, `disposition="needs_parent"`,
  and a non-empty reason.
- Both calls failed with `E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED`.
- The error was `No module named 'daemon_core'`.
- The message stayed `unseen`; parent prompt was not submitted.
- This means side triage judgment was correct. The failure is runtime import/root propagation.

Code path:

1. `tools/launcher/env_tool_mcp_server.py` receives native MCP `message__mark`.
2. It routes through `runtime_kernel.client.request_runtime_broker("env.tool", params)`.
3. The broker dispatches through `scripts/runtime_kernel/dispatcher.py`.
4. `_runtime_server_env()` currently derives `BUDDYSWITCH_REPO_ROOT` from
   `manifest_path.parents[1]`.
5. Live broker startup passes the projected workspace manifest:
   `ACTOR_INSTANCE_ROOT/workspace/buddyswitch/manifest.toml`.
6. Therefore `BUDDYSWITCH_REPO_ROOT` becomes `ACTOR_INSTANCE_ROOT/workspace`.
7. `scripts/env/tool_runtime/context.py::_launcher_dir_for_runtime()` looks for
   `ACTOR_INSTANCE_ROOT/workspace/tools/launcher`.
8. Projected runtime workspaces intentionally do not contain `tools/launcher`.
9. Importing `daemon_core` fails.

## Scope

Fix only the source-root propagation bug.

In scope:

- Runtime broker session must carry an explicit source repo root.
- Launcher broker startup must pass that source repo root.
- Dispatcher must export `BUDDYSWITCH_REPO_ROOT` from the explicit source root when available.
- Tests must prove the projected workspace manifest no longer causes `daemon_core` import failure.

Out of scope:

- No task checkout gate changes.
- No request/track/project-management changes.
- No message disposition changes.
- No fallback that marks `needs_parent` without submitting parent prompt.
- No generic workflow engine, event bus, or compatibility layer.

## Design Decision

Use an explicit broker `repo_root_path` instead of deriving source root from manifest path.

Reason:

- In source-checkout tests, `manifest_path.parents[1]` happens to be the source repo root.
- In live runtime, `manifest_path.parents[1]` is the projected workspace.
- The broker already has a launcher-controlled source root at the MCP config layer and shell
  environment layer.
- Source root is not a property of the projected manifest. It must be passed as first-class runtime
  session context.

Fallback rule:

- If explicit `repo_root_path` is present, use it.
- If absent, keep the current `manifest_path.parents[1]` fallback for existing tests and direct
  developer invocations.
- The explicit path must be normalized with `expanduser().resolve(strict=False)`.

Diagnostics rule:

- For diagnostics, reject or warn when explicit source root does not contain
  `tools/launcher/daemon_core.py`.
- Do not make diagnostics the fix. The hard proof for this bug is
  `message.mark(needs_parent)` succeeding through a broker session that uses a projected manifest.
- Do not require `tools/launcher` inside the projected workspace. That would hide the actual root
  propagation bug.

## Files To Modify

- `scripts/runtime_kernel/dispatcher.py`
  - Add `repo_root_path: Path | None = None` to `RuntimeBrokerSession`.
  - Add a helper that selects source root from `session.repo_root_path` before falling back to
    `manifest_path.parents[1]`.
  - Pass the selected source root into `BUDDYSWITCH_REPO_ROOT`.

- `scripts/runtime_kernel/broker.py`
  - Add optional CLI argument `--repo-root` to `serve`, `ping`, `status`, `ensure`, and `stop`
    subcommands.
  - Pass `repo_root_path=args.repo_root` into `_runtime_session()`, `_dispatch_v2_request()`, and
    `dispatch_runtime_request()`.
  - For `serve`, pass `repo_root_path=args.repo_root` into `RuntimeBrokerConfig`.
  - For `ensure`, pass `repo_root_path=args.repo_root` into `lifecycle.ensure_broker()`.
  - For `ping`, `status`, and `stop`, accepting `--repo-root` is enough; these commands do not need
    to change health/stop semantics.

- `scripts/runtime_kernel/server.py`
  - Add `repo_root_path: Path | None = None` to `RuntimeBrokerConfig`.
  - Include it when creating the session passed to `dispatcher.dispatch_runtime_request`.

- `scripts/runtime_kernel/lifecycle.py`
  - Add `repo_root_path: Path | None = None` to `start_broker_process()` and `ensure_broker()`.
  - Pass `--repo-root` plus `str(repo_root_path)` to the broker `serve` command when provided.

- `tools/launcher/runtime_broker.sh`
  - Pass `--repo-root "${BUDDYSWITCH_REPO_ROOT}"` in `_buddyswitch_runtime_broker_lifecycle_json`.
  - Keep the manifest as the projected workspace manifest unless another existing environment
    variable explicitly overrides it.

- `tests/test_runtime_broker.py`
  - Add focused dispatcher and subprocess broker regressions.

- `tests/test_message_env_tool.py`
  - Add message-level regression proving `needs_parent` succeeds with a projected manifest and a
    source-root `daemon_core.py`.

- `tests/test_buddyswitch_launcher.py`
  - Add or extend launcher coverage to prove broker startup receives `--repo-root`.

- `tests/helpers/fake_codex.py`
  - Include `BUDDYSWITCH_REPO_ROOT` in captured payloads.
  - Pass `--repo-root` plus the captured repo root value in the broker status probe used by
    launcher tests.

## Task 1: Add Dispatcher Regression For Explicit Source Root

**Files:**

- Modify: `tests/test_runtime_broker.py`

Steps:

- [ ] Add `test_env_tool_dispatch_uses_explicit_repo_root_with_projected_manifest`.
- [ ] Create a temporary projected workspace containing `buddyswitch/manifest.toml` but no
  `tools/launcher`.
- [ ] Create a fake source repo root containing `tools/launcher/daemon_core.py`.
- [ ] Build this session:

```python
session = dispatcher.RuntimeBrokerSession(
    instance_json_path=instance_json,
    manifest_path=projected_manifest,
    repo_root_path=fake_source_root,
)
```
- [ ] Patch `runtime_kernel.dispatcher.dispatch_env_tool_request` and capture
  `os.environ["BUDDYSWITCH_REPO_ROOT"]`.
- [ ] Assert the captured value equals `fake_source_root`, not the projected workspace.

Expected current failure:

- Before implementation, `RuntimeBrokerSession` has no `repo_root_path`, or
  `BUDDYSWITCH_REPO_ROOT` is captured as the projected workspace.

Focused command:

```bash
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_dispatch_uses_explicit_repo_root_with_projected_manifest -q
```

## Task 2: Implement Broker Session Source Root

**Files:**

- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `scripts/runtime_kernel/broker.py`
- Modify: `scripts/runtime_kernel/server.py`

Steps:

- [ ] Add `repo_root_path: Path | None = None` to `RuntimeBrokerSession`.
- [ ] Add helper in `dispatcher.py`:

```python
def _runtime_source_repo_root(*, manifest_path: Path, repo_root_path: Path | None) -> Path:
    if repo_root_path is not None:
        return repo_root_path.expanduser().resolve(strict=False)
    return manifest_path.expanduser().resolve(strict=False).parents[1]
```

- [ ] Change `_runtime_server_env()` to accept `repo_root_path` and use this helper.
- [ ] Thread `session.repo_root_path` through `dispatch_runtime_request()`.
- [ ] In `broker.py`, add `repo_root_path: Path | None = None` to `_runtime_session`,
  `_dispatch_v2_request`, and public `dispatch_runtime_request`.
- [ ] `_runtime_session` must construct `dispatcher.RuntimeBrokerSession` with
  `repo_root_path=repo_root_path`.
- [ ] `_dispatch_v2_request` must pass its `repo_root_path` into `_runtime_session`.
- [ ] Public `dispatch_runtime_request` must pass its `repo_root_path` into `_dispatch_v2_request`.

- [ ] Add `--repo-root` to broker CLI parsers for `serve`, `ping`, `status`, `ensure`, and `stop`.
- [ ] In `server.py`, add `repo_root_path` to `RuntimeBrokerConfig`.
- [ ] In `RuntimeBrokerServer.__init__`, create `_session` with
  `repo_root_path=config.repo_root_path`.
- [ ] In `broker.py`, pass `args.repo_root` into:
  - `RuntimeBrokerConfig(repo_root_path=args.repo_root)` for `serve`;
  - `lifecycle.ensure_broker(repo_root_path=args.repo_root)` for `ensure`;
  - `_dispatch_v2_request(repo_root_path=args.repo_root)` and
    `dispatch_runtime_request(repo_root_path=repo_root_path)` for in-process calls.
- [ ] Run the Task 1 focused test until it passes.

No other behavior should change.

## Task 3: Add Message-Level Projected Manifest Regression

**Files:**

- Modify: `tests/test_message_env_tool.py`

Steps:

- [ ] Add `test_message_mark_needs_parent_uses_source_repo_root_when_broker_manifest_is_projected`.
- [ ] Seed a processable inbound message addressed to the active actor.
- [ ] Create a projected workspace with copied runtime surface and `buddyswitch/manifest.toml`, but
  no `tools/launcher`.
- [ ] Create a fake source root with `tools/launcher/daemon_core.py` implementing:
  - `load_daemon_context(instance_json)`
  - `DaemonState.load(*, instance_root, actor_id, main_thread_id)`
  - `DaemonRuntime.submit_parent_prompt(prompt, *, handler_name, origin_id, interrupt_policy)`
- [ ] Dispatch `message.mark(needs_parent)` through `runtime_kernel.dispatcher.dispatch_runtime_request()`
  with:
  - `manifest_path=projected_workspace / "buddyswitch" / "manifest.toml"`
  - `RuntimeBrokerSession.repo_root_path=fake_source_root`
  - active actor matching the message recipient
- [ ] Use this request shape:

```python
request = {
    "protocol": BROKER_V2_PROTOCOL,
    "request_id": "req-message-needs-parent-projected-root",
    "method": "env.tool",
    "params": {
        "actor_id": "act-dev-projected-broker-parent",
        "active_role": "dev",
        "tool": "message",
        "action": "mark",
        "args": {
            "message_id": seed["id"],
            "disposition": "needs_parent",
            "reason": "This changes the active parent-thread objective.",
        },
    },
    "deadline_ms": 35000,
}
session = dispatcher.RuntimeBrokerSession(
    instance_json_path=instance_json,
    manifest_path=projected_manifest,
    repo_root_path=fake_source_root,
)
response = dispatcher.dispatch_runtime_request(request, session)
```
- [ ] Assert:
  - response `ok` is true;
  - response includes parent request details;
  - stored message disposition is `needs_parent`;
  - stored `disposition_reason` is the requested reason;
  - fake `daemon_core` saw `handler_name == "message_mark"`;
  - fake `daemon_core` saw `origin_id == message_id`;
  - fake `daemon_core` saw `interrupt_policy == "before_submit"`.

Expected current failure:

- Before implementation, the call fails with `E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED` and
  `No module named 'daemon_core'`, or there is no way to pass explicit repo root into the broker
  session.

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_mark_needs_parent_uses_source_repo_root_when_broker_manifest_is_projected -q
```

## Task 4: Implement Launcher Broker Root Propagation

**Files:**

- Modify: `scripts/runtime_kernel/broker.py`
- Modify: `scripts/runtime_kernel/lifecycle.py`
- Modify: `tools/launcher/runtime_broker.sh`

Steps:

- [ ] Add optional `repo_root_path` argument to `lifecycle.start_broker_process()`.
- [ ] Add optional `repo_root_path` argument to `lifecycle.ensure_broker()`.
- [ ] In `start_broker_process()`, append the two command elements `--repo-root` and
  `str(repo_root_path)` to the `serve` command when `repo_root_path` is provided.
- [ ] In `broker.py`, pass `args.repo_root` from `ensure` into `lifecycle.ensure_broker()`.
- [ ] In `tools/launcher/runtime_broker.sh`, pass `--repo-root "${BUDDYSWITCH_REPO_ROOT}"` to
  the common `_buddyswitch_runtime_broker_lifecycle_json` invocation used by `status`, `ensure`,
  and `stop`.
- [ ] Preserve current projected manifest behavior:

```bash
--manifest "${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml"
```

- [ ] Run focused runtime broker tests.

Focused command:

```bash
python3 -m pytest tests/test_runtime_broker.py -q
```

## Task 5: Add Live Subprocess Broker Regression

**Files:**

- Modify: `tests/test_runtime_broker.py`

Steps:

- [ ] Add `test_live_broker_needs_parent_uses_repo_root_with_workspace_manifest`.
- [ ] Use existing `_sync_runtime_surface(workspace_dir)` to create a projected broker workspace.
- [ ] Ensure `workspace_dir / "tools"` does not exist.
- [ ] Create `fake_source_root / "tools" / "launcher" / "daemon_core.py"`.
- [ ] The fake `submit_parent_prompt` must write its call payload to
  `Path(context.instance_root) / "runtime" / "parent-request.json"` so the parent handoff can be
  asserted from the test process.
- [ ] Write one processable message JSON into
  `workspace_dir / "state" / "buddyswitch" / "objects" / "messages" / "msg-live-projected-root.json"`:

```json
{
  "id": "msg-live-projected-root",
  "from_actor_address": {"actor_id": "act-dev-bbbbbbbbbbbb", "role_id": "dev"},
  "to_actor_address": {"actor_id": "act-pm-aaaaaaaaaaaa", "role_id": "pm"},
  "content": "This changes the active parent-thread objective.",
  "reply_to": null,
  "created_at": "2026-06-04T00:00:00Z",
  "disposition": "unseen",
  "disposition_reason": null,
  "disposition_updated_at": null,
  "processed_by_actor_address": null
}
```

- [ ] Write `instance.json` with `actor_id="act-pm-aaaaaaaaaaaa"`, `role="pm"`, `status="active"`,
  `workspace_dir=str(workspace_dir)`, and `instance_root=str(workspace_dir)`.
- [ ] Extend `_run_broker_cli` so its keyword arguments include:

```python
repo_root_path: Path | None = None
```

- [ ] Append the two command elements `--repo-root` and `str(repo_root_path)` to the subprocess
  command when `repo_root_path` is not `None`.
- [ ] Start the broker with:

```python
ensure_completed, ensure_payload = self._run_broker_cli(
    workspace_dir=workspace_dir,
    command="ensure",
    paths=paths,
    instance_json=instance_json,
    manifest_path=manifest_path,
    repo_root_path=fake_source_root,
)
self.assertEqual(ensure_completed.returncode, 0, msg=ensure_completed.stderr)
self.assertTrue(ensure_payload.get("ok"), msg=ensure_payload)
```

- [ ] Send an `env.tool` request over the broker socket with
  `runtime_kernel.protocol.write_message` and read the response with
  `runtime_kernel.protocol.read_message`:

```python
request = {
    "protocol": BROKER_V2_PROTOCOL,
    "request_id": "req-live-needs-parent-projected-root",
    "method": "env.tool",
    "params": {
        "actor_id": "act-pm-aaaaaaaaaaaa",
        "active_role": "pm",
        "tool": "message",
        "action": "mark",
        "args": {
            "message_id": "msg-live-projected-root",
            "disposition": "needs_parent",
            "reason": "This changes the active parent-thread objective.",
        },
    },
    "deadline_ms": 35000,
}
```

- [ ] Assert the response is successful and the stored message becomes `needs_parent`.
- [ ] Assert `workspace_dir / "runtime" / "parent-request.json"` contains:
  - `"handler_name": "message_mark"`
  - `"origin_id": "msg-live-projected-root"`
  - `"interrupt_policy": "before_submit"`
- [ ] Stop the broker in `finally`.

Expected current failure:

- Without the fix, the subprocess broker derives source root from the workspace manifest and cannot
  import `daemon_core`.

Focused command:

```bash
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_broker_needs_parent_uses_repo_root_with_workspace_manifest -q
```

## Task 6: Add Launcher Coverage For `--repo-root`

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/helpers/fake_codex.py`

Steps:

- [ ] In `tests/helpers/fake_codex.py`, capture:

```python
"repo_root": os.environ.get("BUDDYSWITCH_REPO_ROOT"),
```

- [ ] In `maybe_capture_broker_probe()`, append these CLI args when `entry["repo_root"]` is a
  non-empty string:

```python
"--repo-root",
str(entry["repo_root"]),
```

- [ ] Extend `test_runtime_broker_starts_from_sparse_workspace` or add a nearby test.
- [ ] Assert captured launch payload includes:

```python
self.assertEqual(Path(payload["repo_root"]).resolve(strict=False), ROOT.resolve(strict=False))
```

- [ ] Assert the broker status probe succeeds after the probe passes `--repo-root`:

```python
self.assertEqual(status_probe["returncode"], 0, msg=status_probe)
self.assertTrue(status_payload.get("healthy"), msg=status_payload)
```

- [ ] Assert `status_probe["stderr"]` does not contain:

```text
unrecognized arguments: --repo-root
```

- [ ] Assert the projected workspace still contains:

```text
scripts/runtime_kernel/broker.py
buddyswitch/manifest.toml
```

- [ ] Assert the projected workspace still does not require:

```text
tools/launcher
```

Focused command:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_starts_from_sparse_workspace -q
```

## Task 7: Verification

Run focused checks first:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_mark_needs_parent_uses_source_repo_root_when_broker_manifest_is_projected -q
python3 -m pytest tests/test_runtime_broker.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_starts_from_sparse_workspace -q
```

Run relevant broader checks:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py -q
git diff --check
```

Full suite check for broad regression risk:

```bash
python3 -m pytest -q
```

Manual live validation after code lands:

1. Start or reuse a market actor coordinator.
2. Send it a message that materially changes its active parent-thread objective.
3. Confirm side thread calls `message__mark` with `disposition="needs_parent"` and a non-empty
   reason.
4. Confirm the tool response has `ok=true`, not `E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED`.
5. Confirm parent thread receives `[MESSAGE NEEDS PARENT]`.
6. Confirm parent thread processes the same message with `message__get`.
7. Confirm final disposition becomes `absorbed` or `replied`.

## Completion Criteria

- `needs_parent` from stdio MCP -> runtime broker -> message tool succeeds with projected workspace
  manifest and explicit source repo root.
- No `No module named 'daemon_core'` occurs on the covered path.
- Broker source root and runtime workspace remain separate facts.
- Existing runtime workspace sparse boundary remains intact; `tools/launcher` is not added to the
  projected workspace.
- Message prompt-first semantics remain unchanged: parent prompt submit succeeds before saving
  `needs_parent`.
- The message remains unchanged if parent prompt submit fails.

## Self-Review

- Spec coverage: covers the observed live failure, the broker root propagation bug, and reliable
  regression coverage for dispatcher, subprocess broker, message tool, and launcher startup.
- Placeholder scan: no implementation step depends on unspecified future design.
- Type consistency: final names are `RuntimeBrokerSession.repo_root_path`,
  `BUDDYSWITCH_REPO_ROOT`, `message.mark(needs_parent)`, `daemon_core`,
  `handler_name="message_mark"`, `origin_id`, and `interrupt_policy="before_submit"`.
