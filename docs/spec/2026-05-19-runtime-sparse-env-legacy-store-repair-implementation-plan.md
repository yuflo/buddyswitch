# Runtime Sparse Env Legacy Store Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore `./buddyswitch-codex instance start --buddy pm` after `da21c47` by making the launcher sparse runtime workspace include the new required `scripts/env_legacy_store.py` module.

**Architecture:** Keep this as a runtime surface sync fix. `env_legacy_store.py` is already the active legacy object API module; the launcher must project it into execution workspaces just like `env_store.py`. Do not change permission hardening, broker protocol, env service behavior, or runtime architecture.

**Tech Stack:** Bash launcher sparse checkout config, Python unittest/pytest launcher tests, runtime broker smoke tests.

---

## Scope

This is a small bugfix, not a redesign.

Modify only:

- `tools/launcher/workspace.sh`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_runtime_broker.py`

Do not modify:

- `tools/launcher/codex_config.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_env_layer_boundaries.py`
- env service/repo behavior
- permission profile logic

Those belong to the separate runtime workspace write permission hardening task.

## Current Failure

The sparse runtime workspace omits `scripts/env_legacy_store.py`. Broker startup then fails before Codex launches:

```text
ModuleNotFoundError: No module named 'env_legacy_store'
```

The import path is:

```text
runtime_kernel.broker
runtime_kernel.dispatcher
env.tools.router
env.tools.dispatch
env.services.artifacts
env.domain.artifact_visibility
env.repos.artifacts
env_legacy_store
```

## Task 1: Reproduce the Regression

**Files:** none

- [ ] **Step 1: Run the focused failing launcher smoke tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_runtime_broker_starts_from_sparse_workspace \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_pm_runtime_commands_work_after_sparse_execution_workspace \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_execution_workspace_is_sparse_runtime_surface
```

Expected before the fix: FAIL, with `ModuleNotFoundError: No module named 'env_legacy_store'`.

- [ ] **Step 2: Confirm the failure is sparse-surface only**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import importlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "scripts"))
for name in ("runtime_kernel.broker", "env.client", "browser_evidence"):
    importlib.import_module(name)
print("source runtime imports ok")
PY
```

Expected before and after the fix: `source runtime imports ok`.

## Task 2: Add `env_legacy_store.py` to the Runtime Sparse Surface

**Files:**

- Modify: `tools/launcher/workspace.sh`

- [ ] **Step 1: Add the file to `buddyswitch_workspace_execution_sparse_paths`**

In `tools/launcher/workspace.sh`, update the sparse path block from:

```bash
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_manifest.py
```

to:

```bash
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_legacy_store.py
scripts/env_manifest.py
```

- [ ] **Step 2: Add the file to runtime workspace validity sentinels**

In the `required_runtime_file` loop, update:

```bash
scripts/env/client.py \
scripts/runtime_kernel/broker.py \
scripts/turn_runtime.py \
buddyswitch/manifest.toml \
framework/contracts/pm.md
```

to:

```bash
scripts/env/client.py \
scripts/runtime_kernel/broker.py \
scripts/turn_runtime.py \
scripts/env_legacy_store.py \
buddyswitch/manifest.toml \
framework/contracts/pm.md
```

## Task 3: Sync Launcher Test Expectations

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add the file to `_RUNTIME_SPARSE_PATHS`**

Update:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env_manifest.py",
```

to:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env_legacy_store.py",
"scripts/env_manifest.py",
```

- [ ] **Step 2: Add the file to `_assert_pm_runtime_shape`**

Update:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env_manifest.py",
```

to:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env_legacy_store.py",
"scripts/env_manifest.py",
```

- [ ] **Step 3: Add the file to the explicit runtime surface check list**

In the runtime surface loop that already checks `scripts/env/tools/dispatch.py` and service files, add:

```python
"scripts/env_legacy_store.py",
```

Keep it near `scripts/env/tools/dispatch.py` so future reviewers see the top-level runtime dependency.

## Task 4: Sync Runtime Broker Test Fixture

**Files:**

- Modify: `tests/test_runtime_broker.py`

- [ ] **Step 1: Add the file to `_sync_runtime_surface`**

Update:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env",
```

to:

```python
"scripts/turn_runtime.py",
"scripts/env_store.py",
"scripts/env_legacy_store.py",
"scripts/env",
```

This keeps lifecycle tests aligned with the launcher runtime surface.

## Task 5: Focused Verification

**Files:** none

- [ ] **Step 1: Run the focused launcher sparse smoke tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_runtime_broker_starts_from_sparse_workspace \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_pm_runtime_commands_work_after_sparse_execution_workspace \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_execution_workspace_is_sparse_runtime_surface
```

Expected after the fix: OK.

- [ ] **Step 2: Run the runtime broker lifecycle fixture tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_runtime_broker.RuntimeBrokerLifecycleTests
```

Expected after the fix: OK.

- [ ] **Step 3: Run the direct user path**

Run:

```bash
./buddyswitch-codex instance start --buddy pm debug prompt-input "runtime sparse smoke"
```

Expected after the fix: command reaches Codex/fake-codex launch path without `ModuleNotFoundError: No module named 'env_legacy_store'`.

If this command opens an interactive session in a real local environment, stop it after confirming broker startup succeeds.

## Review Acceptance

Reviewer should verify:

- `scripts/env_legacy_store.py` is present in the launcher sparse path list.
- `scripts/env_legacy_store.py` is present in runtime workspace validity checks.
- `tests/test_buddyswitch_launcher.py` no longer blesses the stale sparse list.
- `tests/test_runtime_broker.py` fixture copies the same runtime surface.
- No permission-profile files were changed.
- No env service behavior was changed.
- Focused launcher sparse smoke tests pass.
- Runtime broker lifecycle tests pass.

## Done Criteria

The task is done when:

- `./buddyswitch-codex instance start --buddy pm` no longer fails on `env_legacy_store`.
- The focused sparse workspace tests pass.
- The fix remains limited to runtime surface projection and matching tests.
- The separate write-permission hardening plan remains untouched.
