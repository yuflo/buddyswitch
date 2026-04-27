# BuddySwitch Instance Lifecycle CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow `buddyswitch-codex` lifecycle CLI so users can discover valid buddies, list stored instances, reopen an existing instance, and delete one stored instance without wiping shared BuddySwitch state.

**Architecture:** Keep the current product-mode model: `start --buddy <buddy>` creates a fresh buddy-locked instance under `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>`, shared canonical state remains under `${BUDDYSWITCH_SHARED_ROOT}/state`, and all launcher mutations serialize through `${BUDDYSWITCH_SHARED_ROOT}.lock`. Add explicit CLI management around the existing instance records rather than introducing smart reuse, a buddy management system, or workspace rebuild policy.

**Tech Stack:** Bash launcher (`buddyswitch-codex`, `tools/launcher/*.sh`), Python manifest/runtime helpers, pytest launcher regression tests.

---

## Status

Draft plan for user confirmation.

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/instance-lifecycle-plan`

## Preflight Gate

### Target Outcome And Current Bottleneck

The current bottleneck is not instance creation. The launcher already creates isolated buddy-locked instance worktrees. The bottleneck is lifecycle continuity: after a user closes the Codex CLI process, there is no product-facing way to find, reopen, or delete the stored instance.

Solving this advances the core product loop because a BuddySwitch instance becomes a reusable work surface rather than a mostly one-shot launch artifact.

### Confirmed Facts

- `buddyswitch-codex` help exposes `start`, `reset`, `browser`, and `workspace`, but no buddy or instance lifecycle commands.
  Evidence: `buddyswitch-codex:22-38`.
- `start --buddy <buddy>` generates a fresh random instance id on every launch.
  Evidence: `buddyswitch-codex:88-92`, `tools/launcher/env.sh:176-179`.
- The launcher already binds instance-specific `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`, `BUDDYSWITCH_WORKSPACE_DIR`, `HOME`, `CODEX_HOME`, and `XDG_CONFIG_HOME`.
  Evidence: `tools/launcher/env.sh:161-173`.
- `instance.json` already stores `instance_id`, `buddy`, `status`, current task/track binding, workspace path, browser port, and timestamps.
  Evidence: `tools/launcher/env.sh:190-215`, `docs/whiteboard/2026-04-23-multi-instance-buddy-runtime-architecture.md:304-316`.
- Product-mode runtime validation already treats `BUDDYSWITCH_INSTANCE_JSON` as the session binding authority.
  Evidence: `scripts/switch_runtime.py:104-151`.
- Plain user text continuation already depends on the stored instance task/track binding.
  Evidence: `scripts/switch_runtime.py:222-233`.
- `reset --yes` deletes the whole shared root; cleanup supports global and buddy/project scopes, not exact instance deletion.
  Evidence: `buddyswitch-codex:309-312`, `scripts/cleanup_buddyswitch.sh:68-103`.
- Shared state projection paths inside instance workspaces are symlinks into `${BUDDYSWITCH_SHARED_ROOT}/state`.
  Evidence: `tools/launcher/workspace.sh` installs projected state paths.
- `scripts/env_manifest.py list-buddies` already provides read-only buddy discovery.
  Evidence: `scripts/env_manifest.py:675-679`.

### Open Assumptions

- It is acceptable for `instance open <id>` to reopen the same execution environment but not restore the prior Codex transcript or terminal scrollback.
- It is acceptable to add a new JSON launcher marker containing `instance_id` while still recognizing legacy pid-only markers during the transition.
- Target-scoped `instance delete <id> --yes` is acceptable if it fails closed whenever a live legacy pid-only launcher marker prevents attribution.
- This first cut can keep text output only. JSON output, TUI, and Context Panel integration are not required for the lifecycle bottleneck.

### Boundaries And Non-Goals

- `buddy list` is read-only manifest discovery. It does not create, edit, delete, rename, enable, disable, or configure buddies.
- `start --buddy <buddy>` remains fresh instance creation. It must not auto-select or reuse an inactive instance.
- `instance open <id>` launches Codex in an existing instance environment. It does not restore the previous Codex transcript.
- `instance delete <id> --yes` deletes only the selected instance's launcher-owned local tree and registered git worktree. It must not delete `${BUDDYSWITCH_SHARED_ROOT}/state`.
- Do not add instance labels, favorites, bulk prune, retention policy, workspace sync/rebuild for old instances, GUI/TUI, daemon supervision, or in-session buddy switching.

### Tools And Permissions

- Use the existing worktree at `/Users/chen/Dev/buddyswitch/.worktrees/instance-lifecycle-plan`.
- Use `apply_patch` for file edits.
- Use pytest for verification.
- Escalate only if local socket or subprocess behavior is blocked by sandbox permissions.

### Verification Plan

Success requires targeted launcher tests for command discovery, buddy list, instance list, instance open, and instance delete, followed by relevant cleanup/runtime guard tests. The final verification command should be:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_cmd_resolve_product_mode_plain_text_with_task_and_track_binding_adapts_to_task_track_switch \
  -q
```

Baseline note: in this planning worktree, the existing targeted test `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow` currently fails at legacy `start` returning exit code 1 before any plan edits. Treat that as a baseline risk to recheck before implementation rather than evidence from this plan.

## Command Contract

Add these product-facing commands:

```bash
./buddyswitch-codex buddy list
./buddyswitch-codex start --buddy <buddy> [codex args...]
./buddyswitch-codex instance list [--buddy <buddy>]
./buddyswitch-codex instance open <instance-id> [codex args...]
./buddyswitch-codex instance delete <instance-id> --yes
```

Command meanings:

- `buddy list`: read `buddyswitch/manifest.toml` and print valid buddy ids, labels, and scopes.
- `start --buddy <buddy>`: create a fresh instance and launch Codex there.
- `instance list`: list stored instances from `${BUDDYSWITCH_SHARED_ROOT}/instances/*/instance.json`.
- `instance open <instance-id>`: launch Codex in the existing instance environment using the same instance id and binding record.
- `instance delete <instance-id> --yes`: remove only the target instance root after safety checks.

Explicitly deferred commands:

- `instance show`
- `instance resume`
- `instance rename`
- `instance prune`
- `instance sync`
- `buddy create`
- `buddy delete`
- `buddy edit`

## File Map

- Modify `buddyswitch-codex`: source the new instance helper, expose `buddy` and `instance` subcommands, route locked instance entrypoints, and print created-instance next-step commands.
- Create `tools/launcher/instance.sh`: instance record loading, instance list formatting, target liveness checks, target delete safety, and instance command parsing.
- Modify `tools/launcher/env.sh`: write new-format launcher marker JSON with `instance_id`, read/count both JSON and legacy pid markers, and keep cleanup compatible.
- Modify `tools/launcher/browser_cockpit.sh`: expose target instance browser liveness checks reusable by `instance delete`.
- Modify `README.md`: document fresh create, existing instance open, instance delete, and buddy discovery.
- Modify `tests/test_buddyswitch_launcher.py`: add lifecycle CLI tests.
- Modify `tests/test_cleanup_system.py` only if implementation touches shared cleanup behavior.
- Modify `docs/whiteboard/2026-04-23-multi-instance-buddy-runtime-architecture.md` only to mark the old "resume/reopen out of scope" and "no per-instance maintenance" statements as superseded by this focused lifecycle CLI plan.

## Task 1: Command Surface And Docs Tests

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `buddyswitch-codex`
- Modify: `README.md`

- [ ] **Step 1: Add failing help coverage for the lifecycle command surface**

Extend `BuddySwitchLauncherTests.test_launcher_help_and_reset_flow` to require the new commands:

```python
self.assertIn("buddy list", help_result.stdout)
self.assertIn("instance list", help_result.stdout)
self.assertIn("instance open", help_result.stdout)
self.assertIn("instance delete", help_result.stdout)
self.assertIn("start --buddy", help_result.stdout)
```

- [ ] **Step 2: Run the focused help test and confirm it fails for missing command text**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  -q
```

Expected: FAIL because current help does not mention `buddy list` or `instance`.

- [ ] **Step 3: Add top-level help text for `buddy` and `instance`**

In `buddyswitch-codex::print_help()`, update the usage block to include:

```text
  buddyswitch-codex buddy list
  buddyswitch-codex instance list [--buddy <buddy>]
  buddyswitch-codex instance open <instance-id> [codex args...]
  buddyswitch-codex instance delete <instance-id> --yes
```

Update the commands block to include:

```text
  buddy   Inspect static BuddySwitch buddies from the manifest.
  instance Manage stored BuddySwitch product-mode instances.
```

- [ ] **Step 4: Add README command contract**

In `README.md`, replace the misleading reuse warning near the product-mode start example with this contract:

````markdown
`start --buddy <buddy>` creates a fresh buddy-locked instance. To re-enter a stored instance, use:

```bash
./buddyswitch-codex instance list
./buddyswitch-codex instance open <instance-id>
```

To remove one stored instance without deleting shared BuddySwitch state:

```bash
./buddyswitch-codex instance delete <instance-id> --yes
```
````

- [ ] **Step 5: Run the focused help test again**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  -q
```

Expected: PASS for help assertions once the unrelated baseline `start` behavior is healthy.

## Task 2: Buddy List

**Files:**
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add a failing test for `buddy list`**

Add this test method to `BuddySwitchLauncherTests`:

```python
def test_buddy_list_prints_manifest_buddies_without_runtime_mutation(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        source_home_path = Path(source_home)
        shared_root = source_home_path / ".codex-buddyswitch"
        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)

        completed = subprocess.run(
            [str(LAUNCHER), "buddy", "list"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("pm", completed.stdout)
        self.assertIn("dev", completed.stdout)
        self.assertIn("market", completed.stdout)
        self.assertFalse(shared_root.exists(), "buddy list must not create runtime state")
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_buddy_list_prints_manifest_buddies_without_runtime_mutation \
  -q
```

Expected: FAIL because `buddy` is currently treated as passthrough Codex args.

- [ ] **Step 3: Implement `buddy list` by reusing `scripts/env_manifest.py`**

In `buddyswitch-codex`, add:

```bash
buddy_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex buddy list
  buddyswitch-codex buddy help

Commands:
  list  Print valid buddies from buddyswitch/manifest.toml.
  help  Show this help message.
EOF
}

buddy_main() {
  local command="${1:-}"
  case "${command}" in
    list)
      shift || true
      if [[ $# -gt 0 ]]; then
        echo "Unknown buddy option: $1" >&2
        buddy_usage >&2
        return 2
      fi
      python3 "${REPO_ROOT}/scripts/env_manifest.py" list-buddies
      ;;
    help|-h|--help)
      buddy_usage
      ;;
    "")
      echo "buddy command is required" >&2
      buddy_usage >&2
      return 2
      ;;
    *)
      echo "Unknown buddy command: ${command}" >&2
      buddy_usage >&2
      return 2
      ;;
  esac
}
```

Add this dispatch case in `main()` before passthrough:

```bash
buddy)
  shift || true
  buddy_main "$@"
  ;;
```

- [ ] **Step 4: Run the buddy list test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_buddy_list_prints_manifest_buddies_without_runtime_mutation \
  -q
```

Expected: PASS.

## Task 3: Instance Records, Launcher Markers, And Liveness Helpers

**Files:**
- Create: `tools/launcher/instance.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add tests for new-format launcher markers and legacy marker compatibility**

Add a test that starts `start --buddy pm` with fake Codex/browser and asserts a launcher marker exists before workspace bootstrap with JSON content containing `pid`, `instance_id`, `buddy`, and `workspace_dir`. Update any existing marker tests that assume only `launcher-*.pid` exists.

The assertion should accept the new marker shape:

```python
markers = list((shared_root / "run").glob("launcher-*.json"))
self.assertEqual(len(markers), 1)
marker = json.loads(markers[0].read_text(encoding="utf-8"))
self.assertEqual(marker["instance_id"], payload["instance_id"])
self.assertEqual(marker["buddy"], "pm")
self.assertEqual(marker["workspace_dir"], str(instance_root / "workspace"))
```

Add a separate test that seeds a legacy `launcher-<pid>.pid` marker and verifies global reset still treats it as active.

- [ ] **Step 2: Run marker tests and confirm they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_writes_launcher_marker_before_workspace_bootstrap \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_is_blocked_when_active_launcher_marker_exists \
  -q
```

Expected: FAIL for JSON marker expectations.

- [ ] **Step 3: Change launcher marker writing to JSON while retaining legacy reads**

In `tools/launcher/env.sh`, replace pid-only marker writing with JSON when launcher metadata is available:

```bash
buddyswitch_write_launcher_marker() {
  local marker_pid="${1:-${BUDDYSWITCH_LAUNCHER_MARKER_PID:-$$}}"
  local marker_path="${BUDDYSWITCH_RUN_STATE_DIR}/launcher-${marker_pid}.json"
  mkdir -p "${BUDDYSWITCH_RUN_STATE_DIR}"
  python3 - "${marker_path}" "${marker_pid}" "${BUDDYSWITCH_START_INSTANCE_ID:-}" "${BUDDYSWITCH_START_BUDDY:-}" "${BUDDYSWITCH_WORKSPACE_DIR:-}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "pid": int(sys.argv[2]),
    "instance_id": sys.argv[3] or None,
    "buddy": sys.argv[4] or None,
    "workspace_dir": sys.argv[5] or None,
    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY
  printf '%s\n' "${marker_path}"
}
```

Update `buddyswitch_count_active_launchers()` to scan both `launcher-*.json` and `launcher-*.pid`, delete stale markers, and count each live pid once.

- [ ] **Step 4: Create `tools/launcher/instance.sh` with read-only record helpers**

Add helper functions:

```bash
#!/usr/bin/env bash
set -euo pipefail

buddyswitch_instance_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex instance list [--buddy <buddy>]
  buddyswitch-codex instance open <instance-id> [codex args...]
  buddyswitch-codex instance delete <instance-id> --yes
  buddyswitch-codex instance help

Commands:
  list    List stored product-mode instances.
  open    Launch Codex in an existing inactive instance.
  delete  Delete one stored inactive instance without deleting shared state.
  help    Show this help message.
EOF
}

buddyswitch_instance_json_files() {
  local instance_json
  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    printf '%s\n' "${instance_json}"
  done
}
```

This file will grow in later tasks; keep it focused on instance lifecycle operations.

- [ ] **Step 5: Source the helper from `buddyswitch-codex`**

At the top of `buddyswitch-codex`, add:

```bash
INSTANCE_HELPER="${REPO_ROOT}/tools/launcher/instance.sh"
```

Validate and source it after browser helper sourcing:

```bash
if [[ ! -f "${ENV_HELPER}" || ! -f "${WORKSPACE_HELPER}" || ! -f "${BROWSER_HELPER}" || ! -f "${INSTANCE_HELPER}" ]]; then
  echo "Launcher helpers are missing under tools/launcher." >&2
  exit 1
fi

source "${INSTANCE_HELPER}"
```

- [ ] **Step 6: Run marker tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_writes_launcher_marker_before_workspace_bootstrap \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_is_blocked_when_active_launcher_marker_exists \
  -q
```

Expected: PASS.

## Task 4: Instance List

**Files:**
- Modify: `tools/launcher/instance.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing tests for empty and populated instance list**

Add:

```python
def test_instance_list_empty_points_to_start_buddy(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        env = os.environ.copy()
        env["HOME"] = str(Path(source_home))
        env.pop("CODEX_HOME", None)

        completed = subprocess.run(
            [str(LAUNCHER), "instance", "list"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("No BuddySwitch instances found.", completed.stdout)
        self.assertIn("./buddyswitch-codex start --buddy <buddy>", completed.stdout)
```

Add:

```python
def test_instance_list_prints_stored_instances_and_filters_by_buddy(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        source_home_path = Path(source_home)
        shared_root = source_home_path / ".codex-buddyswitch"
        for instance_id, buddy, task_id in (
            ("inst-pm-a", "pm", "task-pm-a"),
            ("inst-dev-b", "dev", "task-dev-b"),
        ):
            instance_root = shared_root / "instances" / instance_id
            instance_root.mkdir(parents=True, exist_ok=True)
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "buddy": buddy,
                        "status": "inactive",
                        "current_task_id": task_id,
                        "current_track_id": None,
                        "workspace_dir": str(instance_root / "workspace"),
                        "browser_port": None,
                        "created_at": "2026-04-26T00:00:00Z",
                        "updated_at": "2026-04-26T00:00:01Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)

        completed = subprocess.run(
            [str(LAUNCHER), "instance", "list", "--buddy", "pm"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("inst-pm-a", completed.stdout)
        self.assertIn("pm", completed.stdout)
        self.assertIn("task-pm-a", completed.stdout)
        self.assertNotIn("inst-dev-b", completed.stdout)
```

- [ ] **Step 2: Run instance list tests and confirm they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_empty_points_to_start_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_prints_stored_instances_and_filters_by_buddy \
  -q
```

Expected: FAIL because `instance` is not routed yet.

- [ ] **Step 3: Implement list parsing and output**

In `tools/launcher/instance.sh`, add a list implementation that:

- accepts optional `--buddy <buddy>`
- validates buddy through `buddyswitch_validate_buddy_id`
- scans instance JSON records
- prints columns: `instance_id`, `buddy`, `status`, `current_task_id`, `current_track_id`, `browser_port`, `updated_at`, `workspace_dir`
- prints an empty-state message when no records match

Use Python for JSON parsing inside the shell helper:

```bash
buddyswitch_instance_list() {
  local buddy_filter=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --buddy)
        [[ $# -ge 2 && -n "${2:-}" && "${2:-}" != --* ]] || {
          echo "Missing value for --buddy" >&2
          buddyswitch_instance_usage >&2
          return 2
        }
        buddy_filter="$2"
        buddyswitch_validate_buddy_id "${buddy_filter}" || return $?
        shift 2
        ;;
      *)
        echo "Unknown instance list option: $1" >&2
        buddyswitch_instance_usage >&2
        return 2
        ;;
    esac
  done

  python3 - "${BUDDYSWITCH_SHARED_ROOT}" "${buddy_filter}" <<'PY'
import json
import sys
from pathlib import Path

shared_root = Path(sys.argv[1])
buddy_filter = sys.argv[2]
rows = []
for instance_json in sorted((shared_root / "instances").glob("*/instance.json")):
    try:
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except Exception as exc:
        rows.append((instance_json.parent.name, "invalid", "invalid", "", "", "", "", f"invalid-json:{exc}"))
        continue
    buddy = payload.get("buddy")
    if buddy_filter and buddy != buddy_filter:
        continue
    rows.append(
        (
            payload.get("instance_id", instance_json.parent.name),
            buddy or "",
            payload.get("status", ""),
            payload.get("current_task_id") or "",
            payload.get("current_track_id") or "",
            str(payload.get("browser_port") or ""),
            payload.get("updated_at", ""),
            payload.get("workspace_dir", ""),
        )
    )

if not rows:
    print("No BuddySwitch instances found.")
    print("Start one with: ./buddyswitch-codex start --buddy <buddy>")
    raise SystemExit(0)

print("instance_id\tbuddy\tstatus\tcurrent_task_id\tcurrent_track_id\tbrowser_port\tupdated_at\tworkspace_dir")
for row in rows:
    print("\t".join(str(item) for item in row))
PY
}
```

- [ ] **Step 4: Route `instance list`**

In `tools/launcher/instance.sh`, add:

```bash
buddyswitch_instance_main() {
  local command="${1:-}"
  case "${command}" in
    list)
      shift || true
      buddyswitch_instance_list "$@"
      ;;
    help|-h|--help)
      buddyswitch_instance_usage
      ;;
    "")
      echo "instance command is required" >&2
      buddyswitch_instance_usage >&2
      return 2
      ;;
    *)
      echo "Unknown instance command: ${command}" >&2
      buddyswitch_instance_usage >&2
      return 2
      ;;
  esac
}
```

In `buddyswitch-codex::main()`, add:

```bash
instance)
  shift || true
  buddyswitch_instance_main "$@"
  ;;
```

- [ ] **Step 5: Run instance list tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_empty_points_to_start_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_prints_stored_instances_and_filters_by_buddy \
  -q
```

Expected: PASS.

## Task 5: Instance Open

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/env.sh`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add failing test for reopening an existing instance**

Add a launcher test that:

1. Starts `start --buddy pm` with fake Codex/browser and captures `instance_id`.
2. Runs `instance open <instance_id> debug prompt-input "continue"` with the same fake environment.
3. Asserts both fake Codex captures use the same `instance_id`, same `instance_json`, same `cwd`, same `HOME`, same `CODEX_HOME`, and no additional `instances/*` directory appears.

Core assertions:

```python
first_payload = json.loads(first_capture.read_text(encoding="utf-8"))
instance_id = first_payload["instance_id"]
open_result = subprocess.run(
    [str(LAUNCHER), "instance", "open", instance_id, "debug", "prompt-input", "continue"],
    cwd=ROOT,
    env=open_env,
    text=True,
    capture_output=True,
    check=False,
)
self.assertEqual(open_result.returncode, 0, msg=open_result.stderr)
second_payload = json.loads(second_capture.read_text(encoding="utf-8"))
self.assertEqual(second_payload["instance_id"], instance_id)
self.assertEqual(second_payload["instance_json"], first_payload["instance_json"])
self.assertEqual(second_payload["cwd"], first_payload["cwd"])
self.assertEqual(second_payload["home"], first_payload["home"])
self.assertEqual(second_payload["codex_home"], first_payload["codex_home"])
self.assertEqual(len(list((shared_root / "instances").glob("inst-*"))), 1)
stored = json.loads(Path(second_payload["instance_json"]).read_text(encoding="utf-8"))
self.assertEqual(stored["status"], "inactive")
```

- [ ] **Step 2: Add failing product-mode binding test for reopened env**

In `tests/test_switch_runtime.py`, add a test that seeds an instance JSON with `current_task_id` and `current_track_id`, sets product-mode env, and confirms plain text adapts through the existing binding:

```python
def test_reopened_product_mode_env_uses_existing_instance_binding(self) -> None:
    instance_json = self._write_instance_json(
        instance_id="inst-pm-reopen",
        current_task_id="task-pm-onboarding",
        current_track_id="track-onboarding",
    )
    env = self._product_env("pm", "inst-pm-reopen", instance_json)
    result = self._run_cmd_resolve(
        "continue the plan",
        extra_env=env,
    )
    payload = result[1]
    self.assertEqual(payload["switch"]["task_id"], "task-pm-onboarding")
    self.assertEqual(payload["switch"]["track_id"], "track-onboarding")
```

Use the existing test helper signatures in `SwitchRuntimeCliProductModeTests`; adjust the call shape to match the current helper methods.

- [ ] **Step 3: Run open and binding tests and confirm they fail only on missing open command**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_reuses_existing_instance_environment \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_reopened_product_mode_env_uses_existing_instance_binding \
  -q
```

Expected: launcher open test FAILS because command is missing. Runtime binding test should PASS if it only asserts existing runtime behavior; if it fails, fix the test helper call before changing runtime code.

- [ ] **Step 4: Implement locked open bootstrap**

In `buddyswitch-codex`, add a public `instance open` path that resolves the target record, binds the instance env, and calls a locked private entrypoint before launching Codex:

```bash
instance_open() {
  local instance_id="$1"
  shift || true
  buddyswitch_validate_instance_id "${instance_id}" || return $?
  buddyswitch_env_bind_instance "${instance_id}" || return $?
  BUDDYSWITCH_OPEN_INSTANCE_ID="${instance_id}" \
    buddyswitch_with_runtime_lock "${REPO_ROOT}/buddyswitch-codex" "__locked-instance-open-bootstrap" || return $?
  cd "${BUDDYSWITCH_WORKSPACE_DIR}"
  BUDDYSWITCH_ACTIVE_BUDDY="${BUDDYSWITCH_OPEN_BUDDY}" \
  BUDDYSWITCH_INSTANCE_ID="${instance_id}" \
  BUDDYSWITCH_INSTANCE_JSON="${BUDDYSWITCH_INSTANCE_JSON}" \
    buddyswitch_run_codex "$@"
}
```

The exact shell variable handoff can be implemented by having the locked entrypoint print the buddy id or by re-reading `instance.json` after the locked bootstrap. Do not store the buddy in an unvalidated user-provided variable.

- [ ] **Step 5: Implement the locked open rules**

In the locked open entrypoint:

1. `buddyswitch_require_runtime_lock`.
2. Validate the instance id.
3. Load `${BUDDYSWITCH_SHARED_ROOT}/instances/<id>/instance.json`.
4. Require `payload.instance_id == id`.
5. Require `payload.buddy` exists in `buddyswitch/manifest.toml`.
6. Require the workspace exists and is a valid execution worktree with `buddyswitch_workspace_is_valid_execution_worktree`.
7. Fail closed if a live new-format marker already belongs to the target instance.
8. Fail closed if a live legacy pid-only launcher marker exists and attribution is impossible.
9. Bind instance env, install the buddy prompt, ensure state projections, bootstrap browser/MCP, and mark `instance.json.status = active`.
10. Publish a new-format launcher marker containing the target `instance_id`.

Open must not call `buddyswitch_workspace_force_rebuild_execution_worktree` or refresh to repo `HEAD`.

- [ ] **Step 6: Ensure inactive cleanup after Codex exits**

Reuse the existing inactive cleanup pattern:

```bash
buddyswitch_with_runtime_lock \
  "${REPO_ROOT}/buddyswitch-codex" \
  "__locked-instance-set-inactive" \
  "${instance_id}"
```

The open command should propagate the Codex exit code unless inactive cleanup fails after a successful Codex exit.

- [ ] **Step 7: Run open and binding tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_reuses_existing_instance_environment \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_reopened_product_mode_env_uses_existing_instance_binding \
  -q
```

Expected: PASS.

## Task 6: Instance Open Failure Modes

**Files:**
- Modify: `tools/launcher/instance.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing tests for invalid open inputs**

Add tests for:

- traversal id: `instance open ../bad`
- missing record: `instance open inst-pm-missing`
- `instance.json` id mismatch
- unknown buddy in `instance.json`
- missing workspace
- live marker for same target instance
- live legacy pid-only marker
- direct locked entrypoint without runtime lock

Each test should assert the exit code and a clear error substring:

```python
self.assertEqual(completed.returncode, 2)
self.assertIn("Invalid instance id", completed.stderr)
```

For missing or unsafe workspace:

```python
self.assertEqual(completed.returncode, 3)
self.assertIn("Instance open blocked", completed.stderr)
self.assertIn("delete this instance or start a new one", completed.stderr)
```

- [ ] **Step 2: Run the open failure tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_traversal_instance_id \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_missing_instance_record \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_instance_id_mismatch \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_unknown_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_missing_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_active_target_instance \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_live_legacy_launcher_marker \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_locked_instance_open_entrypoint_rejects_direct_invocation_without_lock \
  -q
```

Expected: FAIL until the validation paths exist.

- [ ] **Step 3: Implement explicit failure messages**

Use these messages:

```text
Instance open blocked: <instance-id> is already active.
Instance open blocked: live legacy launcher marker exists and cannot be attributed to an instance.
Instance open blocked: workspace is missing or invalid for <instance-id>; delete this instance or start a new one.
Instance record missing: <path>
Instance id mismatch in <path>
Unknown buddy '<buddy>'. Valid: ...
```

- [ ] **Step 4: Run open failure tests again**

Run the same command from Step 2.

Expected: PASS.

## Task 7: Instance Delete

**Files:**
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing happy-path delete test**

Add a test that creates two stored instances and shared state, registers the target workspace as a git worktree, runs `instance delete <target> --yes`, and asserts:

- target instance root is removed
- non-target instance root remains
- `${BUDDYSWITCH_SHARED_ROOT}/state` remains
- target workspace is absent from `git worktree list --porcelain`

Core assertions:

```python
self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
self.assertFalse(target_root.exists())
self.assertTrue(other_root.exists())
self.assertTrue((shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json").exists())
worktree_list = subprocess.run(
    ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=False,
)
self.assertNotIn(str(target_workspace), worktree_list.stdout)
```

- [ ] **Step 2: Add failing delete safety tests**

Add tests for:

- missing `--yes` returns 1 and does not delete
- invalid traversal id returns 2 and does not delete
- missing target returns 2
- live target launcher marker returns 3
- live target browser pid returns 3
- live target browser endpoint returns 3
- live legacy pid-only launcher marker returns 3
- worktree deregistration failure returns non-zero and does not blind-delete
- direct locked delete entrypoint without runtime lock returns 2

- [ ] **Step 3: Run delete tests and confirm they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_removes_only_target_instance_without_shared_state \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_requires_yes \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_active_target_launcher \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_active_target_browser_pid \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_live_target_browser_endpoint \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_live_legacy_launcher_marker \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_locked_instance_delete_entrypoint_rejects_direct_invocation_without_lock \
  -q
```

Expected: FAIL because delete does not exist.

- [ ] **Step 4: Expose target browser checks**

In `tools/launcher/browser_cockpit.sh`, add target helpers that do not depend on global instance mode:

```bash
buddyswitch_browser_instance_pid_marker_is_active() {
  local instance_id="$1"
  local marker_file="${BUDDYSWITCH_SHARED_ROOT}/instances/${instance_id}/browser/chrome.pid"
  buddyswitch_browser_pid_marker_is_active "${marker_file}"
}

buddyswitch_browser_instance_endpoint_is_active() {
  local instance_id="$1"
  local instance_json="${BUDDYSWITCH_SHARED_ROOT}/instances/${instance_id}/instance.json"
  local browser_port
  browser_port="$(python3 - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
port = payload.get("browser_port")
if isinstance(port, int):
    print(port)
PY
)"
  [[ -n "${browser_port}" ]] || return 1
  curl --silent --show-error --fail "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1
}
```

- [ ] **Step 5: Implement locked delete**

Delete must:

1. require `--yes`
2. validate the instance id before computing paths
3. acquire the runtime lock
4. require the target record exists and matches the id
5. fail if a live new-format launcher marker belongs to the target
6. fail if any live legacy pid-only marker exists
7. fail if target browser pid or endpoint is active
8. compute `instance_root="${BUDDYSWITCH_SHARED_ROOT}/instances/${instance_id}"`
9. call `buddyswitch_workspace_remove_registered_worktrees_under "${instance_root}"`
10. delete `instance_root`
11. print `Instance deleted: <instance-id>`

Never use `workspace_dir` from `instance.json` as the delete target.

- [ ] **Step 6: Run delete tests**

Run the command from Step 3.

Expected: PASS.

## Task 8: Created Instance Next-Step Output

**Files:**
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing assertion to the existing buddy start lifecycle test**

In `test_start_with_buddy_wires_instance_env_and_lifecycle`, assert stdout contains stable next-step lines:

```python
self.assertIn("BuddySwitch instance:", completed.stdout)
self.assertIn(payload["instance_id"], completed.stdout)
self.assertIn("Open existing:", completed.stdout)
self.assertIn(f"./buddyswitch-codex instance open {payload['instance_id']}", completed.stdout)
self.assertIn("Delete instance:", completed.stdout)
self.assertIn(f"./buddyswitch-codex instance delete {payload['instance_id']} --yes", completed.stdout)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  -q
```

Expected: FAIL because current start suppresses instance identity output.

- [ ] **Step 3: Print next-step lines after locked bootstrap succeeds and before Codex launches**

In `start_codex()`, after locked bootstrap and before `cd "${BUDDYSWITCH_WORKSPACE_DIR}"`, print:

```bash
if [[ -n "${buddy}" ]]; then
  echo "BuddySwitch instance: ${instance_id} (${buddy})"
  echo "Workspace: ${BUDDYSWITCH_WORKSPACE_DIR}"
  echo "Instance record: ${instance_json}"
  echo "Open existing: ./buddyswitch-codex instance open ${instance_id}"
  echo "Delete instance: ./buddyswitch-codex instance delete ${instance_id} --yes"
fi
```

- [ ] **Step 4: Run the focused lifecycle test**

Run the command from Step 2.

Expected: PASS.

## Task 9: Documentation And Superseded Architecture Notes

**Files:**
- Modify: `README.md`
- Modify: `docs/whiteboard/2026-04-23-multi-instance-buddy-runtime-architecture.md`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add repo consistency coverage for lifecycle wording**

Add a test in `tests/test_repo_consistency.py` that asserts README includes:

```python
self.assertIn("./buddyswitch-codex buddy list", readme)
self.assertIn("./buddyswitch-codex instance list", readme)
self.assertIn("./buddyswitch-codex instance open <instance-id>", readme)
self.assertIn("./buddyswitch-codex instance delete <instance-id> --yes", readme)
self.assertIn("creates a fresh buddy-locked instance", readme)
```

Also assert README no longer says `start --buddy <buddy>` reuses an existing instance.

- [ ] **Step 2: Run the consistency test and confirm it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_documents_instance_lifecycle_cli \
  -q
```

Expected: FAIL until README is updated.

- [ ] **Step 3: Update README**

Document the command contract from this plan in the Quick Start and Daily Use sections. Use these exact phrases:

```markdown
`start --buddy <buddy>` creates a fresh buddy-locked instance.
`instance open <instance-id>` re-enters the existing instance workspace and runtime profile; it does not restore the previous Codex transcript.
`instance delete <instance-id> --yes` removes only that instance's launcher-owned local tree and does not delete shared BuddySwitch state.
```

- [ ] **Step 4: Mark old whiteboard exclusions as superseded**

In `docs/whiteboard/2026-04-23-multi-instance-buddy-runtime-architecture.md`, add a short note near the old out-of-scope lines:

```markdown
> Superseded for lifecycle CLI: explicit `instance open <instance-id>` and `instance delete <instance-id> --yes` are now planned as a narrow product-facing lifecycle cut. Smart reuse, broad per-instance maintenance APIs, and workspace rebuild/sync remain out of scope.
```

- [ ] **Step 5: Run docs consistency**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_documents_instance_lifecycle_cli \
  -q
```

Expected: PASS.

## Task 10: Final Verification

**Files:**
- No new files

- [ ] **Step 1: Run command-surface and lifecycle tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_buddy_list_prints_manifest_buddies_without_runtime_mutation \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_empty_points_to_start_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_prints_stored_instances_and_filters_by_buddy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_reuses_existing_instance_environment \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_removes_only_target_instance_without_shared_state \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run safety and cleanup tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_requires_yes \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_active_target_launcher \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_active_target_browser_pid \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_live_target_browser_endpoint \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_live_legacy_launcher_marker \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run runtime binding sanity check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_cmd_resolve_product_mode_plain_text_with_task_and_track_binding_adapts_to_task_track_switch \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_reopened_product_mode_env_uses_existing_instance_binding \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run the final grouped verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_cmd_resolve_product_mode_plain_text_with_task_and_track_binding_adapts_to_task_track_switch \
  tests/test_switch_runtime.py::SwitchRuntimeCliProductModeTests::test_reopened_product_mode_env_uses_existing_instance_binding \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_documents_instance_lifecycle_cli \
  -q
```

Expected: PASS.

If any test requiring local browser/socket binding fails with sandbox-related `PermissionError` or local connection restrictions, rerun the exact same command with approved escalation and record that the first failure was environmental.

## Deferred Work

- Automatic reuse from `start --buddy <buddy>`.
- Instance labels, favorites, rename, retention, and prune.
- JSON output mode for lifecycle commands.
- Context Panel instance management.
- Workspace rebuild/sync for stored instances.
- Target delete while a live legacy pid-only marker exists.
- Codex transcript/session restoration.
- GUI/TUI instance manager.
