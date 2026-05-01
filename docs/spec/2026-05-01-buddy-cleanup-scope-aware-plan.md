# Buddy Cleanup Scope-Aware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `./buddyswitch-codex data cleanup --buddy <buddy>` block only when that same buddy has active launcher or browser state.

**Architecture:** Keep cleanup ownership in `tools/launcher/cleanup.sh`. Parse the cleanup target before active-state checks, then use buddy-scoped active-state helpers only for `--buddy`; keep broad active-state blocking for `--all-data` and `--app-runtime`.

**Tech Stack:** Bash launcher helpers, Python snippets inside shell helpers, `pytest` shell integration tests.

---

## Scope

In scope:

- `data cleanup --buddy <buddy>` ignores active launcher/browser state from other buddies.
- `data cleanup --buddy <buddy>` still blocks active launcher/browser state from the same buddy.
- `data cleanup --all-data` and `data cleanup --app-runtime` keep broad active-state blocking.
- Tests verify CLI behavior through `./buddyswitch-codex data cleanup`, not internal helper calls.

Out of scope:

- Project workspace collaboration changes.
- `instance delete` semantics.
- `runs/raw/<buddy>` cleanup behavior, already confirmed by live scan.

## File Map

- Modify `tests/test_cleanup_system.py`
  Add shell integration tests that create active markers and assert observable cleanup behavior.

- Modify `tools/launcher/cleanup.sh`
  Parse cleanup target before active checks and add buddy-scoped active launcher/browser checks.

- No change to `scripts/env_cleanup.py`
  Its cleanup plan already discovers matching buddy instance `runs/raw/<buddy>`.

## Task 1: Add CLI Behavior Tests For Buddy-Scoped Active Launchers

**Files:**

- Modify: `tests/test_cleanup_system.py`
- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add failing and guard tests**

Add these methods inside `CleanupShellIntegrationTests`, near the existing active cleanup tests:

```python
    def test_shell_buddy_cleanup_allows_other_buddy_active_launcher(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-cleanup", "pm")
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-market.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "instance_id": "inst-market-active",
                    "buddy": "market",
                    "workspace_dir": str(self.shared_root / "instances" / "inst-market-active" / "workspace"),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "buddy")
        self.assertIn(
            "instances/inst-pm-cleanup/workspace/runs/raw/pm/pm.log",
            payload["result"]["deleted_paths"],
        )
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_blocks_same_buddy_active_launcher(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-active-cleanup", "pm")
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-pm.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "instance_id": "inst-pm-active-cleanup",
                    "buddy": "pm",
                    "workspace_dir": str(pm_workspace),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active buddyswitch-codex instance", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_allows_other_buddy_active_launcher -q
```

Expected:

```text
FAILED ... AssertionError: 3 != 0
```

Reason: current cleanup blocks before checking the target buddy.

- [ ] **Step 3: Run the same-buddy guard test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_blocks_same_buddy_active_launcher -q
```

Expected:

```text
1 passed
```

This guard prevents relaxing cleanup so far that it mutates the target buddy while that buddy is active.

## Task 2: Add CLI Behavior Tests For Buddy-Scoped Active Browsers

**Files:**

- Modify: `tests/test_cleanup_system.py`
- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add browser marker tests**

Add these methods inside `CleanupShellIntegrationTests`, near the launcher tests from Task 1:

```python
    def test_shell_buddy_cleanup_allows_other_buddy_active_browser_marker(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-browser-cleanup", "pm")
        market_root, _ = self._create_instance_workspace("inst-market-browser-active", "market")
        browser_marker = market_root / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "buddy")
        self.assertIn(
            "instances/inst-pm-browser-cleanup/workspace/runs/raw/pm/pm.log",
            payload["result"]["deleted_paths"],
        )
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_blocks_same_buddy_active_browser_marker(self) -> None:
        pm_root, pm_workspace = self._create_instance_workspace("inst-pm-browser-active", "pm")
        browser_marker = pm_root / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())
```

- [ ] **Step 2: Run the failing browser test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_allows_other_buddy_active_browser_marker -q
```

Expected:

```text
FAILED ... AssertionError: 3 != 0
```

Reason: current cleanup treats any instance browser pid marker as global.

- [ ] **Step 3: Run the same-buddy browser guard test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_blocks_same_buddy_active_browser_marker -q
```

Expected:

```text
1 passed
```

## Task 3: Implement Buddy-Scoped Active Checks In Cleanup

**Files:**

- Modify: `tools/launcher/cleanup.sh`
- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add a launcher-count helper**

Add this helper above `buddyswitch_count_active_browsers` in `tools/launcher/cleanup.sh`:

```bash
buddyswitch_count_active_launchers_for_buddy() {
  local buddy="$1"
  if [[ ! -d "${BUDDYSWITCH_RUN_STATE_DIR}" ]]; then
    echo "0"
    return
  fi

  python3 - "${BUDDYSWITCH_RUN_STATE_DIR}" "${BUDDYSWITCH_SHARED_ROOT}" "${buddy}" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
shared_root = Path(sys.argv[2])
target_buddy = sys.argv[3]
live_pids = set()


def pid_is_live(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def marker_matches_target(payload):
    buddy = payload.get("buddy")
    if buddy == target_buddy:
        return True
    instance_id = payload.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        return False
    instance_json = shared_root / "instances" / instance_id / "instance.json"
    try:
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except Exception:
        return False
    return instance_payload.get("buddy") == target_buddy


for marker in run_dir.glob("launcher-*.json"):
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        pid = payload.get("pid")
    except Exception:
        marker.unlink(missing_ok=True)
        continue
    if not isinstance(pid, int) or pid <= 0 or not pid_is_live(pid):
        marker.unlink(missing_ok=True)
        continue
    if marker_matches_target(payload):
        live_pids.add(pid)

print(len(live_pids))
PY
}
```

- [ ] **Step 2: Add a browser-count helper**

Add this helper below `buddyswitch_count_active_browsers` in `tools/launcher/cleanup.sh`:

```bash
buddyswitch_count_active_browsers_for_buddy() {
  local buddy="$1"
  local instance_json instance_id instance_buddy

  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    instance_buddy="$(
      python3 - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
buddy = payload.get("buddy")
if isinstance(buddy, str):
    print(buddy)
PY
    )"
    [[ "${instance_buddy}" == "${buddy}" ]] || continue
    instance_id="$(basename "$(dirname "${instance_json}")")"
    if buddyswitch_browser_instance_pid_marker_is_active "${instance_id}"; then
      echo "1"
      return 0
    fi
    if buddyswitch_browser_instance_endpoint_is_active "${instance_id}"; then
      echo "1"
      return 0
    fi
  done

  echo "0"
}
```

- [ ] **Step 3: Parse cleanup target before active checks**

Replace `buddyswitch_cleanup_run_locked` in `tools/launcher/cleanup.sh` with this structure:

```bash
buddyswitch_cleanup_run_locked() {
  local state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  local target_root=""
  local target_scope=""
  local active_count active_browser_count

  buddyswitch_require_runtime_lock
  buddyswitch_cleanup_validate_shared_root || return $?
  buddyswitch_cleanup_parse_args "$@" || return $?

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "buddy" ]]; then
    active_count="$(buddyswitch_count_active_launchers_for_buddy "${BUDDYSWITCH_CLEANUP_BUDDY}")"
  else
    active_count="$(buddyswitch_count_active_launchers)"
  fi
  if [[ "${active_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
    echo "Close active launcher sessions and retry." >&2
    return 3
  fi

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "buddy" ]]; then
    active_browser_count="$(buddyswitch_count_active_browsers_for_buddy "${BUDDYSWITCH_CLEANUP_BUDDY}")"
  else
    active_browser_count="$(buddyswitch_count_active_browsers)"
  fi
  if [[ "${active_browser_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_browser_count} active browser instance(s) detected." >&2
    echo "Close active browser sessions and retry." >&2
    return 3
  fi

  target_root="${state_root}"
  target_scope="${BUDDYSWITCH_CLEANUP_SCOPE}"

  cd "${BUDDYSWITCH_CLEANUP_REPO_ROOT}"
  buddyswitch_cleanup_run_env_cleanup "${target_root}" "${target_scope}"
}
```

- [ ] **Step 4: Run shell syntax check**

Run:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh
```

Expected:

```text
no output, exit code 0
```

## Task 4: Verify Behavior And Guard Scope

**Files:**

- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Run the four buddy cleanup tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_allows_other_buddy_active_launcher \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_blocks_same_buddy_active_launcher \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_allows_other_buddy_active_browser_marker \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_buddy_cleanup_blocks_same_buddy_active_browser_marker \
  -q
```

Expected:

```text
4 passed
```

- [ ] **Step 2: Run cleanup integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Confirm no source-checkout cleanup drift**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_cleanup_surfaces_use_data_cleanup_command -q
```

Expected:

```text
1 passed
```

## Self-Review

- Spec coverage: The plan covers the only active optimization item for cleanup: `--buddy` scope-aware active-state blocking.
- Test integrity: Tests call the public CLI and assert user-visible cleanup outcomes and preserved files. They do not bypass cleanup helpers or assert implementation internals.
- Scope control: The plan does not change project workspace behavior, instance deletion, or `runs/raw/<buddy>` cleanup.
