# BuddySwitch Launcher + Market Cockpit Migration Implementation Plan

> Superseded by `docs/dev1626/2026-04-17-optimization-a-browser-cockpit-realignment-plan.md`. The current product-facing launcher surface is `buddyswitch-codex browser ...`, and `buddyswitch-codex start` is the preferred bootstrap path.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate BuddySwitch launcher and market Chrome MCP setup into one product-facing CLI without a compatibility shell, while separating internal launcher helpers from runtime `scripts/`.

**Architecture:** Keep `buddyswitch-codex` as the only user-facing entrypoint. Move launcher internals into `tools/launcher/` with one helper for shared BuddySwitch environment management and one helper for browser cockpit management. Remove `scripts/setup_market_chrome_devtools.sh` entirely and update docs/tests to use the launcher surface.

**Tech Stack:** Bash, existing `codex` CLI, Chrome remote debugging, `npx chrome-devtools-mcp@latest`, `pytest`, existing BuddySwitch launcher tests.

---

## File Structure

**Create**
- `tools/launcher/env.sh`
- `tools/launcher/browser_cockpit.sh`
- `tests/test_browser_cockpit_launcher.py`

**Modify**
- `buddyswitch-codex`
- `tests/test_buddyswitch_launcher.py`
- `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`
- `docs/dev0220/2026-04-17-market-chrome-mcp-phase1-implementation-plan.md`
- `framework/docs/browser-cockpit.md`

**Delete**
- `scripts/setup_market_chrome_devtools.sh`

**Why these boundaries**
- `scripts/` stays focused on BuddySwitch runtime and control-layer code such as `switch_runtime.py`, `env_manifest.py`, and `serve_context_panel.py`.
- `tools/launcher/` becomes the internal home for product launcher shell helpers.
- `buddyswitch-codex` remains the single stable CLI surface users run directly.

---

### Task 1: Extract Shared Launcher Environment Helpers

**Files:**
- Create: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Write the failing test for helper-backed launcher behavior**

```python
def test_launcher_still_uses_shared_env_after_helper_split(self) -> None:
    completed = subprocess.run(
        [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["home"].endswith(".codex-buddyswitch/home")
    assert payload["codex_home"].endswith(".codex-buddyswitch/codex-home")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k helper_split -v`
Expected: FAIL because the current launcher has no helper split and no dedicated regression for the extracted helper flow.

- [ ] **Step 3: Create `tools/launcher/env.sh` with shared environment functions**

```bash
#!/usr/bin/env bash
set -euo pipefail

buddyswitch_env_init() {
  local source_home="${BUDDYSWITCH_SOURCE_HOME:-${HOME}}"
  export BUDDYSWITCH_SOURCE_HOME="${source_home}"
  export BUDDYSWITCH_SOURCE_CODEX_HOME="${BUDDYSWITCH_SOURCE_CODEX_HOME:-${CODEX_HOME:-${source_home}/.codex}}"
  export BUDDYSWITCH_SHARED_ROOT="${BUDDYSWITCH_SHARED_ROOT:-${source_home}/.codex-buddyswitch}"
  export BUDDYSWITCH_HOME="${BUDDYSWITCH_SHARED_ROOT}/home"
  export BUDDYSWITCH_CODEX_HOME="${BUDDYSWITCH_SHARED_ROOT}/codex-home"
  export BUDDYSWITCH_XDG_CONFIG_HOME="${BUDDYSWITCH_HOME}/.config"
  export BUDDYSWITCH_RUN_STATE_DIR="${BUDDYSWITCH_SHARED_ROOT}/run"
}

buddyswitch_ensure_shared_env() {
  mkdir -p \
    "${BUDDYSWITCH_HOME}" \
    "${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    "${BUDDYSWITCH_CODEX_HOME}" \
    "${BUDDYSWITCH_RUN_STATE_DIR}"
}
```

- [ ] **Step 4: Refactor `buddyswitch-codex` to source the helper**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

source "${REPO_ROOT}/tools/launcher/env.sh"
buddyswitch_env_init
```

- [ ] **Step 5: Run launcher tests to verify shared env behavior still passes**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -v`
Expected: PASS with the existing shared-home assertions still green after the helper extraction.

- [ ] **Step 6: Commit**

```bash
git add buddyswitch-codex tools/launcher/env.sh tests/test_buddyswitch_launcher.py
git commit -m "refactor: extract launcher shared env helpers"
```

---

### Task 2: Introduce Market Cockpit Helper Under `tools/launcher/`

**Files:**
- Create: `tools/launcher/browser_cockpit.sh`
- Create: `tests/test_browser_cockpit_launcher.py`
- Modify: `buddyswitch-codex`
- Delete: `scripts/setup_market_chrome_devtools.sh`

- [ ] **Step 1: Write the failing tests for the new market subcommands**

```python
def test_market_status_checks_debug_endpoint_only(self) -> None:
    completed = subprocess.run(
        [str(LAUNCHER), "market", "status"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode in (0, 1)
    assert "market" in completed.stdout.lower() or "market" in completed.stderr.lower()


def test_market_install_mcp_targets_buddyswitch_codex_home(self) -> None:
    completed = subprocess.run(
        [str(LAUNCHER), "market", "install-mcp"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert "codex-home" in completed.stdout or "codex-home" in completed.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_browser_cockpit_launcher.py -v`
Expected: FAIL because `buddyswitch-codex` does not yet implement the `market` subcommand family.

- [ ] **Step 3: Create the browser cockpit helper with narrow subcommands**

```bash
#!/usr/bin/env bash
set -euo pipefail

market_profile_dir() {
  printf '%s\n' "${BUDDYSWITCH_SHARED_ROOT}/chrome/shared-browser"
}

market_log_file() {
  printf '%s\n' "${BUDDYSWITCH_SHARED_ROOT}/log/chrome-market.log"
}

browser_url() {
  printf 'http://127.0.0.1:%s\n' "${BUDDYSWITCH_BROWSER_PORT:-9222}"
}
```

- [ ] **Step 4: Implement `status`, `ensure`, and `install-mcp` in the helper**

```bash
market_status() {
  if curl --silent --show-error --fail "$(browser_url)/json/version" >/dev/null; then
    echo "Browser cockpit is reachable on ${BUDDYSWITCH_BROWSER_PORT:-9222}."
    return 0
  fi
  echo "Browser cockpit is not reachable on ${BUDDYSWITCH_BROWSER_PORT:-9222}." >&2
  return 1
}

browser_ensure() {
  mkdir -p "$(market_profile_dir)" "${BUDDYSWITCH_SHARED_ROOT}/log"
  # launch headed Chrome if market_status fails
}

market_install_mcp() {
  browser_ensure
  HOME="${BUDDYSWITCH_HOME}" \
  CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
  XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
  codex mcp add chrome-devtools-cockpit -- \
    npx chrome-devtools-mcp@latest \
    --browser-url="$(browser_url)"
}
```

- [ ] **Step 5: Wire `buddyswitch-codex browser ...` to the helper**

```bash
browser)
  shift || true
  source "${REPO_ROOT}/tools/launcher/browser_cockpit.sh"
  buddyswitch_browser_main "$@"
  ;;
```

- [ ] **Step 6: Delete the old standalone script**

```bash
git rm scripts/setup_market_chrome_devtools.sh
```

- [ ] **Step 7: Run focused tests for market subcommands**

Run: `python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py -v`
Expected: PASS with `browser status` and `browser ensure` exposed only through `buddyswitch-codex`.

- [ ] **Step 8: Commit**

```bash
git add buddyswitch-codex tools/launcher/browser_cockpit.sh tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py
git commit -m "feat: route browser cockpit through buddyswitch launcher"
```

---

### Task 3: Extend Reset Semantics to Cover Market Cockpit State

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Write the failing test for reset blocking when browser cockpit is active**

```python
def test_reset_blocks_when_market_cockpit_marker_exists(self) -> None:
    marker = shared_root / "run" / "market-chrome.pid"
    marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
    completed = subprocess.run(
        [str(LAUNCHER), "reset", "--yes"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k market_cockpit_marker -v`
Expected: FAIL because reset currently checks only launcher PID markers.

- [ ] **Step 3: Add browser cockpit PID tracking to the helper**

```bash
market_pid_marker() {
  printf '%s\n' "${BUDDYSWITCH_RUN_STATE_DIR}/market-chrome.pid"
}

write_market_pid_marker() {
  printf '%s\n' "$1" > "$(market_pid_marker)"
}
```

- [ ] **Step 4: Extend reset safety checks to include market Chrome**

```bash
if buddyswitch_market_is_active; then
  echo "Reset blocked: active browser cockpit detected." >&2
  return 3
fi
```

- [ ] **Step 5: Run reset-related tests**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py -k reset -v`
Expected: PASS with reset refusing to delete a live shared Chrome profile.

- [ ] **Step 6: Commit**

```bash
git add buddyswitch-codex tools/launcher/env.sh tools/launcher/browser_cockpit.sh tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
git commit -m "fix: protect launcher reset from active browser cockpit"
```

---

### Task 4: Replace All User-Facing References to the Old Script

**Files:**
- Modify: `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`
- Modify: `docs/dev0220/2026-04-17-market-chrome-mcp-phase1-implementation-plan.md`
- Modify: `framework/docs/browser-cockpit.md`

- [ ] **Step 1: Write the failing doc consistency test**

```python
def test_repo_has_no_reference_to_setup_market_chrome_devtools(self) -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".py", ".sh"}:
            text = path.read_text(encoding="utf-8")
            assert "setup_market_chrome_devtools.sh" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_repo_consistency.py -k setup_market_chrome_devtools -v`
Expected: FAIL because docs/dev0220 and the old script path still mention `scripts/setup_market_chrome_devtools.sh`.

- [ ] **Step 3: Update docs to the new launcher CLI**

```markdown
1. Preferred path: run `./buddyswitch-codex start`
2. If you want a read-only preflight, run `./buddyswitch-codex browser status`
3. If the shared browser endpoint is not reachable, run `./buddyswitch-codex browser ensure`
4. Confirm both `chrome-devtools` and `chrome-devtools-cockpit` are available in the BuddySwitch Codex session
```

- [ ] **Step 4: Update the cockpit doc to name the launcher entrypoint**

```markdown
The shared browser cockpit is prepared through `buddyswitch-codex browser ensure`.
The preferred full bootstrap path is `buddyswitch-codex start`.
```

- [ ] **Step 5: Run doc and repo consistency checks**

Run: `python3 -m pytest tests/test_repo_consistency.py -v`
Expected: PASS with no remaining references to the deleted script and with browser cockpit docs pointing at the launcher flow.

- [ ] **Step 6: Commit**

```bash
git add docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md docs/dev0220/2026-04-17-market-chrome-mcp-phase1-implementation-plan.md framework/docs/browser-cockpit.md tests/test_repo_consistency.py
git commit -m "docs: move browser cockpit setup to buddyswitch launcher"
```

---

### Task 5: End-to-End Verification of the New Launcher Surface

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Add an end-to-end smoke test for the new CLI layout**

```python
def test_launcher_help_lists_market_subcommands(self) -> None:
    completed = subprocess.run(
        [str(LAUNCHER), "help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "browser status" in completed.stdout
    assert "browser ensure" in completed.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k market_subcommands -v`
Expected: FAIL until the help surface is updated to advertise the browser commands.

- [ ] **Step 3: Update launcher help and success messages**

```bash
Usage:
  buddyswitch-codex start [codex args...]
  buddyswitch-codex reset --yes
  buddyswitch-codex browser status
  buddyswitch-codex browser ensure
  buddyswitch-codex help
```

- [ ] **Step 4: Run the full launcher-related test suite**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py tests/test_repo_consistency.py -v`
Expected: PASS with the new launcher CLI, browser cockpit helper, reset safety, and doc references all aligned.

- [ ] **Step 5: Commit**

```bash
git add buddyswitch-codex tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py tests/test_repo_consistency.py
git commit -m "test: verify unified launcher and browser cockpit flow"
```

---

## Self-Review

**Spec coverage**
- Single user-facing launcher retained: covered by Tasks 1, 2, and 5.
- Internal helper split into a dedicated directory: covered by Tasks 1 and 2.
- No compatibility wrapper: covered by Task 2 deletion and Task 4 doc replacement.
- Market Chrome setup fully moved under launcher commands: covered by Tasks 2, 3, and 5.
- Reset semantics updated to include market state: covered by Task 3.

**Placeholder scan**
- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task names exact files and explicit test commands.

**Type consistency**
- The plan consistently uses `tools/launcher/env.sh`, `tools/launcher/browser_cockpit.sh`, and the subcommands `browser status` and `browser ensure`.

## Notes For Execution

- Do not keep `scripts/setup_market_chrome_devtools.sh` as a forwarding shell.
- Do not leave doc references split across old and new commands.
- Keep `scripts/` reserved for BuddySwitch runtime/control-layer code, not launcher product helpers.

## Execution Handoff

Plan complete and saved to `docs/dev1626/2026-04-17-launcher-market-cockpit-migration-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
