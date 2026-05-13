# Runtime Broker V2 Root Fix Memo

Date: 2026-05-13
Worktree: `dev2258`
Scope: BuddySwitch runtime broker v2 launcher lifecycle, runtime workspace boundary, product-mode broker client behavior, stale broker recovery, and verification gates.

## Background

A Market instance became effectively unusable after the runtime broker v2 upgrade. The first product-mode command in the session attempted:

```bash
python3 scripts/turn_runtime.py prepare "帮我看一下 producthunt 上最近有哪些有意思的ai生产力小工具"
```

The command failed before the Market buddy could do useful work. Investigation showed two concrete states:

- The running session was inside a BuddySwitch runtime workspace.
- The runtime broker state was unhealthy: pid was stale, socket marker remained, and the product session could not repair the broker runtime directory without a sandbox approval prompt.

This is a core product-path failure, not a Market research bug.

## Root Cause

The failure is caused by a broken runtime ownership boundary introduced during broker v2.

The intended boundary is:

- Launcher owns broker lifecycle.
- Runtime workspace owns product-mode state writes.
- Product Codex sessions only call the broker socket.
- Source checkout should not be used as the product runtime write root.

The broken v2 behavior violated that boundary:

1. `tools/launcher/runtime_broker.sh` launched broker lifecycle commands from `BUDDYSWITCH_REPO_ROOT`.
2. The broker process imported runtime modules from the source checkout path.
3. `env_store.ROOT` was therefore resolved to the source checkout instead of the instance runtime workspace.
4. `prepare` eventually attempted to save a run reservation.
5. `env_store.require_runtime_workspace_write_root()` rejected the write because it saw the source checkout, not a runtime workspace.
6. Separately, the broker pid/socket/marker entered a stale state.
7. The product Codex profile could connect to the broker socket, but could not safely write `runtime-broker.pid`, `runtime-broker.sock`, `runtime-broker.socket`, or `runtime-broker.log`.
8. The product client stopped with a broker error or requested sandbox approval for repair work that should belong to the launcher.

The important point: the agent's current directory was not the decisive fact. The broker process's import root and cwd were.

## Test Failure

The previous test plan named many of the right acceptance surfaces, but the implemented tests did not enforce the real product boundary.

Main misses:

- Launcher tests mostly used a fake `codex` that captured environment variables. They did not run a real `prepare` from inside the launched runtime workspace.
- Env layer end-to-end tests called `runtime_broker.dispatch_runtime_request()` directly. That bypassed Unix socket transport, broker process cwd, import root, launcher lifecycle, Codex profile, and product sandbox behavior.
- Lifecycle tests patched broker startup and ping helpers. They validated helper logic but did not prove the launcher starts the broker from the runtime workspace.
- Static scans checked that shell health delegated to Python lifecycle, but did not forbid `BUDDYSWITCH_REPO_ROOT` as the broker script/cwd.
- The planned `instance open` stale broker recovery test was not implemented.

This allowed the codebase to pass tests while still shipping a broker that could start from the wrong root.

## Goal

Root-fix broker v2 so product-mode state access is reliable through the shortest verified path:

```text
launcher start/open
  -> ensure broker from instance runtime workspace
  -> product Codex launches in runtime workspace
  -> first prepare succeeds through broker socket
  -> state writes land under runtime workspace
```

The fix is not a one-line stale socket cleanup. The fix is to make broker ownership, startup root, recovery responsibility, and acceptance tests impossible to confuse.

## Non-Goals

Do not:

- grant product Codex sessions broad write access to the instance `runtime/` directory;
- make product-mode client subprocesses repair broker pid/socket/marker state;
- add a generic supervisor, daemon manager, queue, or workflow engine;
- keep source-root and workspace-root broker launch paths side by side;
- preserve broken compatibility with source-checkout broker startup;
- treat manual sandbox approval as a normal recovery path.

## Target Boundary

There should be exactly one normal product-mode broker boundary:

```text
Source checkout
  Owns launcher code and source files.

Launcher process
  Owns instance start/open, broker status, broker cleanup, broker ensure, broker stop.

Runtime workspace
  Owns runtime imports, env_store.ROOT, AGENTS.md runtime marker, and product-mode state writes.

Product Codex session
  Runs inside runtime workspace and calls BUDDYSWITCH_RUNTIME_BROKER_SOCKET.
  Does not mutate broker lifecycle files.
```

## Recommended Fix

### 1. Start broker lifecycle from the runtime workspace

`tools/launcher/runtime_broker.sh` must resolve broker paths from `BUDDYSWITCH_WORKSPACE_DIR`, not `BUDDYSWITCH_REPO_ROOT`.

Required behavior:

- broker script: `${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py`
- manifest: `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml`
- cwd for lifecycle commands: `${BUDDYSWITCH_WORKSPACE_DIR}`

The source checkout may still run the launcher shell, but broker Python execution must happen through the synced runtime surface.

### 2. Make launcher the only lifecycle repair owner

`instance start` and `instance open` should always run launcher-owned broker ensure before launching Codex.

`ensure` must:

- read current status;
- classify stale pid/socket/marker states;
- remove stale pid/socket/marker files;
- start broker from the runtime workspace;
- wait for a real ping, not only socket existence;
- return the socket path only after health is proven;
- leave a clear error with log path on failure;
- avoid leaving stale marker files after failed startup.

Product-mode client code should not run `broker.py ensure` as a recovery path. It should report structured broker unavailable/stale feedback and point back to `./buddyswitch-codex instance open <instance-id>`.

### 3. Make health prove the runtime root

Broker health should prove the broker is not merely alive, but alive in the right runtime root.

`ping` or `status` should expose enough facts for tests and diagnostics:

- protocol;
- pid;
- socket path;
- instance id;
- active buddy;
- broker cwd or resolved runtime root;
- `env_store.ROOT`;
- whether `env_store.is_runtime_workspace()` is true.

Healthy status requires:

- pid is live;
- socket path is a Unix socket;
- marker points to the same socket;
- ping returns expected instance and buddy;
- ping pid matches pid file;
- ping socket path matches marker/socket;
- `env_store.ROOT` equals the instance workspace or resolves inside it;
- runtime workspace marker is valid.

### 4. Keep product client conservative

The product client should keep request retry rules conservative:

- `prepare` should not auto-retry side effects after transport reset.
- `persist` may retry only with idempotency key.
- read-only env tools may retry once.
- stale/missing broker should not trigger product-side lifecycle mutation.

This preserves the product-mode permission boundary and avoids turning every agent session into a broker supervisor.

### 5. Remove dual-root ambiguity

Do not keep both source-root and workspace-root startup paths.

The accepted path is runtime workspace startup. Any source-root fallback should be deleted or blocked by tests. If the runtime surface is missing, launcher should fail before Codex launch with a clear error, not silently use source checkout modules.

## Required Test Gates

Add these tests before or with the implementation. They are the real regression boundary for this incident.

### Gate 1: First prepare after instance start

Launcher test:

1. Start an instance with fake `codex`.
2. Fake `codex` runs from the launched cwd:

   ```bash
   python3 scripts/turn_runtime.py prepare "smoke prepare"
   ```

3. Assert:

   - exit code is 0;
   - stdout is business payload with top-level `ok: true`;
   - stdout is not a broker envelope;
   - run reservation exists under the runtime workspace;
   - broker status reports `env_store.ROOT` as the runtime workspace.

This test must fail if broker imports from the source checkout.

### Gate 2: Stale broker recovery on instance open

Launcher test:

1. Create an inactive instance workspace.
2. Create stale `runtime-broker.pid`, `runtime-broker.socket`, and socket path state.
3. Run:

   ```bash
   ./buddyswitch-codex instance open <instance-id> debug prompt-input continue
   ```

4. Fake `codex` runs `python3 scripts/turn_runtime.py prepare "smoke prepare"`.
5. Assert:

   - open succeeds;
   - stale files were replaced;
   - marker points to the live socket;
   - status is healthy;
   - prepare succeeds.

### Gate 3: Source-root broker startup is forbidden

Static test:

- `tools/launcher/runtime_broker.sh` must not use `${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py` for lifecycle execution.
- `tools/launcher/runtime_broker.sh` must not `cd "${BUDDYSWITCH_REPO_ROOT}"` before running broker lifecycle commands.
- The expected strings must mention `BUDDYSWITCH_WORKSPACE_DIR`.

### Gate 4: Product client does not self-ensure

Client test:

- Simulate stale socket for `prepare`.
- Assert the product client raises structured stale/unavailable feedback.
- Assert it does not call `subprocess.run(["python3", "...", "broker.py", "ensure", ...])`.

### Gate 5: Live broker status proves workspace root

Lifecycle or launcher integration test:

- Start a real broker from a runtime workspace.
- Call `broker.py status`.
- Assert status includes runtime root facts and reports:

  ```json
  {
    "runtime_workspace": true,
    "env_store_root": "<instance>/workspace"
  }
  ```

## Implementation Sequence

Use TDD and keep each step small.

1. Add Gate 3 static test. It should fail on current `dev2258`.
2. Change `tools/launcher/runtime_broker.sh` to use `BUDDYSWITCH_WORKSPACE_DIR` for broker script, manifest, and cwd.
3. Add Gate 5 runtime root status test. It should fail until broker status exposes root facts.
4. Add runtime root facts to broker ping/status.
5. Add Gate 1 first-prepare launcher test. It should fail until the launcher uses workspace broker execution end to end.
6. Fix launcher/broker startup until Gate 1 passes.
7. Add Gate 2 stale-open recovery test. It should fail if stale cleanup or ensure is incomplete.
8. Fix stale cleanup and failed-start cleanup.
9. Add Gate 4 product client test.
10. Remove product-side `_ensure_runtime_broker()` or make it unreachable for product-mode stale/missing broker recovery.
11. Run focused verification.
12. Run broader verification.

## Verification Commands

Focused:

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::<new first prepare test> -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::<new stale open recovery test> -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::<new runtime root status test> -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::<new product client no self ensure test> -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::<new source root forbidden test> -q
```

Broader:

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_task_manager_env_tool.py -q
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
```

Final:

```bash
python3 -m pytest -p no:cacheprovider tests -q
```

## Definition Of Done

This fix is done only when:

- broker lifecycle commands execute from the runtime workspace;
- source-root broker startup is blocked by tests;
- `instance start` followed by first `prepare` works in a launcher-created workspace;
- `instance open` repairs stale broker state before launching Codex;
- broker status proves the runtime workspace root;
- product client does not mutate broker lifecycle files;
- no product-mode path requires sandbox approval to repair broker runtime state;
- focused and broader verification pass.

## Expected Product Outcome

After the fix, a Market instance should be able to start from a clean or stale broker state and immediately run:

```bash
python3 scripts/turn_runtime.py prepare "帮我看一下 producthunt 上最近有哪些有意思的ai生产力小工具"
```

without manual broker diagnosis, without sandbox escalation for broker repair, and without source-checkout write guard failures.
