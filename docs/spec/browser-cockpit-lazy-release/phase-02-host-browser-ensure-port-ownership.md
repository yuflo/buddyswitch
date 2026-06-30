# Phase 02 Host Browser Ensure Port Ownership

## Phase Objective

Make `env browser ensure --instance <actor>` allocate and record a valid actor-owned browser port when `browser_port` is missing, inactive, foreign, or unknown, while preserving explicit `--port` override behavior and never killing a foreign listener.

This phase covers memo Task 3.

## Exact Source Files To Modify

- `buddyswitch-codex`
- `tools/launcher/browser_cockpit.sh`
- `tests/test_buddyswitch_launcher.py`

## Exact Tests To Add Or Update

- Add `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy`.
- Add `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port`.
- Keep `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port` proving explicit `--port` still wins.
- Keep `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_port_before_side_effects`, `test_env_browser_ensure_rejects_invalid_port_before_runtime_lock`, and `test_env_browser_ensure_rejects_invalid_env_port_before_lock_and_side_effects`.

## Current Behavior Evidence

- `buddyswitch-codex:browser_ensure_locked` reads `browser_port` from `instance.json`, exports it when present, then calls `buddyswitch_browser_init_defaults`.
- When `browser_port` is missing, `buddyswitch_browser_init_defaults` sets `BUDDYSWITCH_BROWSER_PORT=9222`.
- `buddyswitch-codex:env_browser_main` validates only port syntax before acquiring the runtime lock; it does not allocate a fresh port when `9222` is already occupied.
- `tools/launcher/browser_cockpit.sh:buddyswitch_browser_allocate_instance_port` already finds a free port in `9222..9321`, but the ensure path only used it from actor start before Phase 1 removed eager startup.
- `tools/launcher/browser_cockpit.sh:buddyswitch_browser_instance_endpoint_ownership_state` already classifies recorded endpoints as `owned`, `foreign`, `unknown`, or `inactive`.

## Target Behavior For This Phase

- If `env browser ensure` is called with explicit `--port`, keep the existing explicit override path.
- If the actor has a recorded port with an owned active endpoint, reuse that port.
- If the actor has a recorded inactive port and the socket is available, reuse that recorded port.
- If the actor has a recorded inactive port but the socket is occupied, allocate a fresh free port.
- If the actor has a recorded foreign or unknown active endpoint, allocate a fresh free port and leave the foreign listener untouched.
- If the actor has no recorded port, allocate the first free port in `9222..9321`, skipping busy sockets such as `9222`.
- After successful ensure, record the selected port in `instance.json`.

## Implementation Steps

1. Add the missing-port test:
   - create an actor record with `browser_port=None`;
   - bind a real listening socket on `127.0.0.1:9222` when available;
   - run `buddyswitch-codex env browser ensure --instance <actor>`;
   - assert `instance.json["browser_port"]` is the next available port, not `9222`;
   - assert fake Chrome argv includes `--remote-debugging-port=<selected>` and `--user-data-dir=<instance>/browser/profile`.
2. Add the foreign-recorded-port test:
   - create actor A with `browser_port=9333`;
   - create actor B with `browser_port=9333` and a live `browser/chrome.pid` marker;
   - fake `curl` to report `9333/json/version` active;
   - fake `lsof` to report a listener pid for `9333`;
   - fake `ps` to report that listener uses actor B profile;
   - run `buddyswitch-codex env browser ensure --instance <actor A>`;
   - assert actor A records a fresh port other than `9333`;
   - assert actor B marker remains.
3. Add `buddyswitch_browser_prepare_instance_ensure_port` in `tools/launcher/browser_cockpit.sh`:
   - inspect `_buddyswitch_browser_instance_recorded_port`;
   - use `buddyswitch_browser_instance_endpoint_ownership_state`;
   - select the recorded port only for owned active or inactive available cases;
   - clear port env and call `buddyswitch_browser_allocate_instance_port` for missing, busy inactive, foreign, or unknown cases.
4. Change `buddyswitch-codex:browser_ensure_locked`:
   - detect whether `--port` appears in the ensure args;
   - for actor ensure without explicit `--port`, call `buddyswitch_browser_prepare_instance_ensure_port`;
   - for explicit `--port`, keep current `browser_main ensure` parsing and recording behavior.
5. Run focused tests and update this phase document with actual results.

## Test Plan

Run the new missing-port test before implementation:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy
```

Expected before implementation: fail because current ensure uses default `9222` instead of allocating away from the busy socket.

Run the new foreign-port test before implementation:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port
```

Expected before implementation: fail because current ensure reuses the recorded foreign `9333` port.

Run the focused phase tests after implementation:

```bash
python3 -m unittest \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_port_before_side_effects \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_port_before_runtime_lock \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_env_port_before_lock_and_side_effects
```

Expected after implementation: pass.

Run the relevant launcher groups:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher
python3 -m unittest tests.test_buddyswitch_launcher
```

Expected after implementation: pass.

Run syntax and diff checks:

```bash
bash -n buddyswitch-codex
bash -n tools/launcher/browser_cockpit.sh
git diff --check
```

Expected after implementation: no output.

## Cleanup Requirements For Service-Starting Tests

- New tests use fake Chrome and fake CDP readiness files; no real Chrome should start.
- The busy-port test closes the bound socket through `addCleanup`.
- The foreign-port test uses fake `curl`, `lsof`, and `ps`; it must leave the foreign actor pid marker in place and remove only temporary directories through the test harness.
- After focused tests, run:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake-chrome|BUDDYSWITCH_TEST|browser-ready\\.flag" || true
```

Expected after implementation: no process attributable to the tests remains.

## Residue Search Terms For This Phase

```bash
rg -n "env browser ensure.*9222|browser_port is missing|reallocates_foreign_recorded_port|allocates_when_instance_port_missing" \
  buddyswitch-codex tools/launcher/browser_cockpit.sh tests/test_buddyswitch_launcher.py
```

Accepted hits after this phase:

- New test names may appear.
- `9222` may remain as the allocation range start and runtime default help text.
- No live ensure code should treat missing `browser_port` as permission to attach to default `9222` without allocation.

## Phase Acceptance Checklist

- [x] Missing actor `browser_port` allocates a free port instead of using busy `9222`.
- [x] Foreign recorded endpoint is not killed and is not reused by the actor.
- [x] Owned active endpoint reuse remains allowed.
- [x] Inactive available recorded port reuse remains allowed.
- [x] Explicit `--port` override still works.
- [x] Invalid port validation still happens before side effects.
- [x] Focused tests pass.
- [x] Relevant launcher test groups pass.
- [x] Bash syntax checks pass.
- [x] Phase residue scan has only accepted hits.

## Verification Evidence

Red checks before implementation:

```text
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy
FAILED (failures=1)
AssertionError: 9222 != 9223

python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port
FAILED (failures=1)
AssertionError: 1 != 0 : Browser cockpit not ready: http://127.0.0.1:9333 (endpoint reachable but no usable page target)
```

Focused phase tests after implementation:

```text
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_port_before_side_effects tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_port_before_runtime_lock tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_rejects_invalid_env_port_before_lock_and_side_effects
Ran 6 tests in 5.271s
OK
```

Broader launcher verification:

```text
python3 -m unittest tests.test_browser_cockpit_launcher
Ran 13 tests in 6.542s
OK

python3 -m unittest tests.test_buddyswitch_launcher
Ran 204 tests in 316.495s
OK
```

Syntax and diff checks:

```text
bash -n buddyswitch-codex
no output

bash -n tools/launcher/browser_cockpit.sh
no output

git diff --check
no output
```

Residue scan:

```text
rg -n "env browser ensure.*9222|browser_port is missing|reallocates_foreign_recorded_port|allocates_when_instance_port_missing" buddyswitch-codex tools/launcher/browser_cockpit.sh tests/test_buddyswitch_launcher.py
```

Accepted hits:

- `tests/test_buddyswitch_launcher.py` contains the two new Phase 2 test names.
- No live launcher code hit the stale missing-port/default-9222 terms.

Process cleanup check:

```text
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake-chrome|BUDDYSWITCH_TEST|browser-ready\\.flag" || true
only the rg command itself matched
```

Remaining risk:

- This phase fixes launcher ensure port ownership only. The cockpit proxy still starts upstream eagerly when launched; that is the next phase.

## Plan Self-Review

- Memo coverage: this phase maps to Task 3 only.
- Test mapping: missing-port allocation, foreign-port reallocation, explicit override, and invalid-port checks are covered by focused tests.
- Process cleanup: fake Chrome and fake ownership helpers avoid real browser startup; busy sockets are closed by test cleanup.
- Rebuild-forward check: the ensure path chooses one current actor-owned endpoint path instead of adding a compatibility flag.
- Boundary check: changes stay inside launcher browser ownership and launcher tests.
