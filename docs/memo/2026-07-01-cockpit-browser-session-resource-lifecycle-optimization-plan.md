# Cockpit Browser Session Resource Lifecycle Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining BuddySwitch actor-owned browser lifecycle gaps so `chrome-devtools-cockpit` / `browser-session` starts, tracks, releases, and stops Chrome/upstream/browser state without residue, while `search.open_browser` stays only a query-to-URL wrapper.

**Architecture:** Browser page ownership remains single-path: `chrome-devtools-cockpit -> cdp_browser_session -> cdp_browser_lifecycle`. Launcher shell owns instance process markers and instance runtime cleanup. Search does not own browser ensure, page open, idle TTL, release, or cleanup.

**Tech Stack:** Bash launcher in `buddyswitch-codex` and `tools/launcher/browser_cockpit.sh`, Python proxy/release handlers in `tools/launcher/`, browser-session helpers in `scripts/env/`, Python unit/integration tests, scoped residue scans, host process residual checks.

---

## Task Goal Restatement

The optimization target is not another browser feature and not a search-tool patch. The target state is:

```text
actor browser work
  -> chrome-devtools-cockpit
  -> browser-session lifecycle
  -> actor-owned Chrome/upstream/runtime markers
  -> deterministic idle release or instance stop cleanup
```

The allowed search path remains:

```text
query + engine
  -> search URL
  -> browser-session open_or_reuse_page
  -> search-specific ToolResult wording
```

The core requirement is forward cleanup: remove the remaining partial lifecycle behavior instead of adding compatibility fallbacks beside it.

## Core Requirements

1. `instance stop` must be a full actor-owned browser cleanup, not only a Chrome marker kill.
2. `env browser ensure` failure must kill the Chrome process it just launched before deleting the marker.
3. `chrome-devtools-cockpit list_pages` must not leave a browser/upstream runtime alive when it was the only browser call and no page is tracked.
4. `browser.cockpit.release` may protect real user pages, but the skip reason must be observable before any retry policy is considered.
5. Host Codex MCP processes such as `chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:9222` remain outside BuddySwitch actor cleanup.
6. `search.open_browser` must remain decoupled from browser lifecycle ownership.

## Bitter Principles Applied

Read sources:

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`

Hard rules for this plan:

- Fix the owner layer: lifecycle fixes go in cockpit/browser-session/launcher cleanup, not role prompts or search tool logic.
- No live surface should teach search-first browser ownership.
- Any test that starts browser/upstream/fake services must prove host resources return to baseline.
- A narrow patch is still wrong if it preserves the wrong boundary.
- Do not add a second cleanup track. Replace partial cleanup semantics with the single full cleanup contract.
- Keep the end-to-end contract alive:

```text
actor asks to browse
  -> cockpit ensures browser-session runtime
  -> actor lists/opens/selects/inspects
  -> idle release or instance stop clears actor-owned runtime state
```

## Current Code Audit

### Confirmed single browser-session path

- `scripts/env/cdp_browser_session.py:128` owns instance browser ensure.
- `scripts/env/cdp_browser_session.py:253` owns `open_or_reuse_page`.
- `scripts/env/cdp_browser_lifecycle.py:457` can schedule `browser.cockpit.release`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:425` routes `new_page` locally through browser-session.
- `scripts/env/tools/search/_impl.py:782-821` builds the search URL, ensures through browser-session, then calls `open_or_reuse_page`.
- `scripts/env/tools/search/tool.py:163` describes `search.open_browser` as asking browser-session to open or reuse.

Scoped scan already confirms no old search-owned browser stack in `scripts/env/tools/search/_impl.py`:

```bash
rg -n '_ensure_browser_runtime|_browser_endpoint|_reload_instance_payload|_open_browser_page|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|cdp_background_page\.py|Target\.createTarget|refresh_page_idle\(|close_page_target\(|evaluate_page_open_gate\(' scripts/env/tools/search/_impl.py || true
```

Expected current result: no matches.

### Remaining lifecycle gaps

1. `buddyswitch-codex:363-379` stops daemon/app-server/broker, then calls `buddyswitch_browser_instance_stop`.
2. `tools/launcher/browser_cockpit.sh:871-894` currently makes `buddyswitch_browser_instance_stop` kill only `browser/chrome.pid`.
3. `tools/launcher/browser_cockpit.sh:956-1002` has complete release pieces, but only `env browser release` uses them after endpoint ownership checks.
4. `tools/launcher/browser_cockpit.sh:667-704` deletes `chrome.pid` after ensure failure but does not terminate the just-launched `chrome_pid`.
5. `tools/launcher/chrome_devtools_cockpit_proxy.py:451-452` marks `list_pages`; `:612-615` appends browser-session state, but does not schedule `browser.cockpit.release` when no tracked page exists.
6. `tools/launcher/browser_release_handler.py:145-146` no-ops when real user pages exist; this is correct protection, but the reason is not observable through the handler result surface.

### Runtime process classification

Current process scan shows many `chrome-devtools-mcp@latest` and watchdog node processes, including wrappers with `--browser-url=http://127.0.0.1:9222`. Current `lsof -nP -iTCP:9222 -sTCP:LISTEN` has no listener. No `chrome_devtools_cockpit_proxy.py` process whose command line points at this `fea-tool` worktree was seen.

Plan implication: do not kill or manage host Codex MCP processes from BuddySwitch actor cleanup. Actor cleanup must only use instance marker files and instance runtime state.

## Scope Boundary

### In scope

- `tools/launcher/browser_cockpit.sh`
- `buddyswitch-codex`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tools/launcher/browser_release_handler.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`
- `tests/test_browser_cockpit_proxy.py`
- `tests/test_browser_page_expired_handler.py`
- `tests/test_browser_lazy_release_integration.py`
- Scoped residue tests or repo consistency tests when they enforce live browser ownership surfaces.

### Out of scope

- No framework or product object redesign.
- No `search.open_browser` browser lifecycle implementation.
- No host Codex MCP cleanup.
- No `diagnose --json` platform feature in this repair package.
- No automatic release retry policy in P0/P1.
- No compatibility mode that preserves the old partial stop behavior.

## Non-Negotiable Replacement Target

`buddyswitch_browser_instance_stop` must stop being a partial Chrome-only cleanup. After implementation, every live caller of `buddyswitch_browser_instance_stop` should get the same actor-owned cleanup semantics:

```text
stop cockpit upstream marker pid/pgid
stop actor Chrome marker pid
delete upstream pid/pgid markers
delete chrome pid marker
delete page_idle.json and page_idle.lock
clear this actor's browser_port
do not kill by shared port
do not kill host or foreign browser resources
```

`env browser release` must call the same cleanup path after it has confirmed ownership. It should not maintain a second copy of the same cleanup sequence.

## Target File Structure

### Launcher cleanup

- Modify `tools/launcher/browser_cockpit.sh`
  - Change `buddyswitch_browser_instance_stop` to the full actor-owned cleanup contract.
  - Keep `buddyswitch_browser_instance_stop_cockpit_upstream`, `_buddyswitch_browser_terminate_pid_value`, and `_buddyswitch_browser_terminate_pgid_value` as local process helpers.
  - Make `buddyswitch_browser_instance_release` call `buddyswitch_browser_instance_stop` for `owned|inactive` endpoints instead of duplicating cleanup.
  - Kill `chrome_pid` on ensure failure before marker removal.

- Modify `buddyswitch-codex`
  - Leave callers on `buddyswitch_browser_instance_stop`; do not add a second `force_cleanup` command.
  - Remove duplicate explicit `buddyswitch_instance_clear_browser_port` calls only where the full stop immediately precedes them and no failure-recording semantics depend on the duplicate.

### Cockpit proxy release scheduling

- Modify `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - In the successful `list_pages` response path, append browser-session state as today.
  - If `page_idle.targets` is empty or absent, schedule `browser.cockpit.release` with reason `page_idle_empty`.
  - If scheduling fails, append a lifecycle warning to the tool response.
  - Do not schedule release when tracked targets remain.

### Release handler observability

- Modify `tools/launcher/browser_release_handler.py`
  - Keep real-user-page protection.
  - Add a direct observable skip reason for `parent_turn_running`, `page_idle_targets_remain`, `browser_port_missing`, and `real_user_page_present`.
  - Prefer daemon log or handler-result evidence already supported by the daemon stack. Do not add retry scheduling here.

## Implementation Plan

### Task 1: Add failing lifecycle regression tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_browser_cockpit_proxy.py`
- Modify: `tests/test_browser_page_expired_handler.py`

- [ ] **Step 1: Add `instance stop` full cleanup regression**

Add a focused launcher test near `test_stop_active_instance_stops_service_broker_browser_and_marks_inactive`:

```python
def test_stop_active_instance_clears_browser_runtime_state(self) -> None:
    upstream_proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    upstream_pgid = os.getpgid(upstream_proc.pid)
    self.addCleanup(self._terminate_registered_process, upstream_proc.pid, upstream_pgid)

    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        ctx = self._start_service_instance(Path(temp_root), Path(source_home))
        completed = ctx["completed"]
        assert isinstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

        instance_root = Path(str(ctx["instance_root"]))
        runtime_browser_dir = instance_root / "runtime" / "browser"
        runtime_browser_dir.mkdir(parents=True, exist_ok=True)
        (runtime_browser_dir / "cockpit-upstream.pid").write_text(f"{upstream_proc.pid}\n", encoding="utf-8")
        (runtime_browser_dir / "cockpit-upstream.pgid").write_text(f"{upstream_pgid}\n", encoding="utf-8")
        (runtime_browser_dir / "page_idle.json").write_text(
            json.dumps({"targets": {}, "page_id_to_target_id": {}}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")

        stop_result = subprocess.run(
            [str(LAUNCHER), "instance", "stop", str(ctx["actor_id"])],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
        upstream_proc.wait(timeout=2)
        self.assertFalse((runtime_browser_dir / "cockpit-upstream.pid").exists())
        self.assertFalse((runtime_browser_dir / "cockpit-upstream.pgid").exists())
        self.assertFalse((runtime_browser_dir / "page_idle.json").exists())
        self.assertFalse((runtime_browser_dir / "page_idle.lock").exists())
        stored = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
        self.assertIsNone(stored["browser_port"])
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_active_instance_clears_browser_runtime_state
```

Expected before implementation: FAIL because upstream marker process and browser runtime state remain after `instance stop`.

- [ ] **Step 2: Add ensure failure launched-process cleanup regression**

Add a launcher test in `tests/test_browser_cockpit_launcher.py`:

```python
def test_browser_ensure_failure_kills_launched_chrome(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
        temp_root_path = Path(temp_root)
        source_home_path = Path(source_home)
        fake_bin = temp_root_path / "bin"
        fake_bin.mkdir(parents=True, exist_ok=True)

        state_file = temp_root_path / "cdp-state.json"
        self._write_cdp_state(
            state_file,
            version_ok=True,
            pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
            allow_background_create_about_blank=False,
        )
        self._write_fake_curl(fake_bin / "curl")
        self._write_exec(
            fake_bin / "fake-chrome",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${BUDDYSWITCH_TEST_CHROME_PID_FILE:-}" ]]; then
  printf '%s\n' "$$" > "${BUDDYSWITCH_TEST_CHROME_PID_FILE}"
fi
sleep 60
""",
        )
        self._write_fake_codex(fake_bin / "codex")
        self._write_fake_background_page_tool(fake_bin / "background-page")

        shared_root = source_home_path / ".codex-buddyswitch"
        actor_id = "act-pm-browser"
        instance_root = self._write_instance_record(shared_root, actor_id)
        chrome_pid_file = temp_root_path / "chrome.pid"

        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
        env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
        env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
        env["BUDDYSWITCH_TEST_CHROME_PID_FILE"] = str(chrome_pid_file)

        ensure = subprocess.run(
            [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(ensure.returncode, 0)
        chrome_pid = int(chrome_pid_file.read_text(encoding="utf-8").strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(chrome_pid, 0)
        self.assertFalse((instance_root / "browser" / "chrome.pid").exists())
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_launcher.py::BrowserCockpitLauncherTests::test_browser_ensure_failure_kills_launched_chrome
```

Expected before implementation: FAIL because the just-launched fake Chrome process remains live.

- [ ] **Step 3: Add `list_pages` empty-state release scheduling regression**

Add a proxy test in `tests/test_browser_cockpit_proxy.py`:

```python
def test_list_pages_with_no_tracked_pages_schedules_release(self) -> None:
    browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

    with tempfile.TemporaryDirectory() as temp_root:
        instance_root = Path(temp_root) / "instances" / "act-dev-browser"
        daemon_core, server, thread = self._start_mailbox(instance_root)

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("list_pages", {})],
            browser_url=browser_url,
            instance_root=instance_root,
        )
        server.close()
        thread.join(timeout=2)

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
        release_schedules = [
            item
            for item in saved["scheduled_triggers"].values()
            if item["trigger_type"] == "browser.cockpit.release"
        ]
        self.assertEqual(len(release_schedules), 1)
        self.assertEqual(release_schedules[0]["payload"], {"reason": "page_idle_empty"})
        self.assertEqual(release_schedules[0]["schedule_key"], "browser.cockpit.release")
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_list_pages_with_no_tracked_pages_schedules_release
```

Expected before implementation: FAIL because `list_pages` appends state but does not schedule `browser.cockpit.release`.

- [ ] **Step 4: Add release skip observability regression**

Add a release-handler test in `tests/test_browser_page_expired_handler.py`:

```python
def test_release_logs_skip_reason_when_real_user_page_exists(self) -> None:
    calls = self._install_launcher_recorder()
    with tempfile.TemporaryDirectory() as temp_root:
        context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
        self._write_page_idle(context.instance_root, {})
        self._install_cdp_targets([{"id": "target-user", "type": "page", "url": "https://example.com/open"}])
        handler = self.release_module.BrowserReleaseHandler()
        with mock.patch("sys.stderr") as stderr:
            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

    self.assertEqual(result.status, "handled")
    self.assertEqual(calls, [])
    self.assertTrue(stderr.write.called)
    written = "".join(str(call.args[0]) for call in stderr.write.call_args_list if call.args)
    self.assertIn("Browser cockpit release skipped: real_user_page_present", written)
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_page_expired_handler.py::BrowserReleaseHandlerTests::test_release_logs_skip_reason_when_real_user_page_exists
```

Expected before implementation: FAIL because the skip reason is not emitted.

### Task 2: Replace partial stop with full actor-owned cleanup

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Change `buddyswitch_browser_instance_stop` semantics**

In `tools/launcher/browser_cockpit.sh`, update `buddyswitch_browser_instance_stop` so it performs full actor-owned cleanup:

```bash
buddyswitch_browser_instance_stop() {
  local actor_id="$1"
  local marker_file marker_pid

  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi

  buddyswitch_browser_instance_stop_cockpit_upstream "${actor_id}"

  marker_file="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/browser/chrome.pid"
  marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
  _buddyswitch_browser_terminate_pid_value "${marker_pid}"
  rm -f "${marker_file}"

  buddyswitch_browser_instance_clear_page_idle_state "${actor_id}"
  buddyswitch_instance_clear_browser_port "${actor_id}"
}
```

This keeps one public cleanup verb and changes its contract forward. Do not add a sibling `force_stop` or compatibility flag.

- [ ] **Step 2: Make release reuse the same cleanup**

In `tools/launcher/browser_cockpit.sh`, replace the `owned|inactive` branch in `buddyswitch_browser_instance_release` with:

```bash
    owned|inactive)
      buddyswitch_browser_instance_stop "${actor_id}"
      echo "Browser cockpit released: ${actor_id}"
      ;;
```

The `foreign|unknown` branch remains port-only:

```bash
    foreign|unknown)
      buddyswitch_instance_clear_browser_port "${actor_id}"
      echo "Browser cockpit release skipped: ${ownership} endpoint on ${recorded_port}; cleared stale browser_port for ${actor_id}"
      ;;
```

- [ ] **Step 3: Remove duplicate clear after immediate full stop**

In `buddyswitch-codex`, remove direct duplicate `buddyswitch_instance_clear_browser_port` calls that immediately follow `buddyswitch_browser_instance_stop` and do not carry separate failure recording. Keep `buddyswitch_instance_record_failure` calls intact.

- [ ] **Step 4: Run stop/release focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_active_instance_clears_browser_runtime_state \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_release_cleans_owned_runtime_state \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_release_clears_foreign_endpoint_port_without_killing_foreign
```

Expected after implementation: PASS.

### Task 3: Kill launched Chrome on ensure failure

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`
- Test: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Terminate launched process before removing marker**

In `buddyswitch_browser_ensure_cockpit_endpoint`, replace the failure cleanup block:

```bash
  rm -f "${marker_file}"
```

with:

```bash
  _buddyswitch_browser_terminate_pid_value "${chrome_pid}"
  rm -f "${marker_file}"
```

Keep the existing endpoint-specific error text after cleanup.

- [ ] **Step 2: Run ensure failure and normal ensure tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_launcher.py::BrowserCockpitLauncherTests::test_browser_ensure_failure_kills_launched_chrome \
  tests/test_browser_cockpit_launcher.py::BrowserCockpitLauncherTests::test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps \
  tests/test_browser_cockpit_launcher.py::BrowserCockpitLauncherTests::test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails
```

Expected after implementation: PASS.

### Task 4: Schedule release after `list_pages` when no page is tracked

**Files:**

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Test: `tests/test_browser_cockpit_proxy.py`

- [ ] **Step 1: Add a local release scheduling helper**

Add a helper near `_browser_session_state_text`:

```python
def _schedule_release_if_no_tracked_pages(root: Path) -> str | None:
    try:
        state = browser_lifecycle._read_page_idle_state(root)
        targets = state.get("targets")
        if isinstance(targets, dict) and targets:
            return None
        browser_lifecycle.schedule_browser_cockpit_release(
            instance_root=root,
            reason="page_idle_empty",
        )
        return None
    except Exception as exc:
        return f"{LIFECYCLE_WARNING_PREFIX} list_pages idle release was not scheduled: {exc}"
```

This helper is deliberately narrow: it only handles the `list_pages` no-tracked-page case and delegates scheduling to browser lifecycle.

- [ ] **Step 2: Call the helper in the successful `list_pages` response path**

In `patch_tool_response_page_use_metadata`, change the `kind == "list_pages"` branch to:

```python
    if kind == "list_pages":
        if not _tool_response_succeeded(message):
            return patched
        state_text = _browser_session_state_text(browser_url=browser_url, instance_root=instance_root)
        patched = patch_tool_response_hint(patched, state_text)
        warning = _schedule_release_if_no_tracked_pages(root)
        if warning:
            patched = patch_tool_response_hint(patched, warning)
        return patched
```

- [ ] **Step 3: Run list_pages focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_list_pages_with_no_tracked_pages_schedules_release \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_list_pages_appends_browser_session_state \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_non_page_use_and_failed_page_response_do_not_refresh_idle
```

Expected after implementation: PASS.

### Task 5: Add release skip reason observability without retry

**Files:**

- Modify: `tools/launcher/browser_release_handler.py`
- Test: `tests/test_browser_page_expired_handler.py`

- [ ] **Step 1: Add a skip logger**

Add this helper:

```python
def _skip(reason: str) -> daemon_core.HandlerResult:
    print(f"Browser cockpit release skipped: {reason}", file=sys.stderr)
    return daemon_core.HandlerResult.handled()
```

- [ ] **Step 2: Use explicit reasons for no-op branches**

In `BrowserReleaseHandler.handle`, replace silent handled no-ops with:

```python
            if _parent_turn_is_running(runtime):
                return _skip("parent_turn_running")
            root = _instance_root(context)
            if root is None:
                return _skip("instance_root_missing")
            if _page_idle_targets(root):
                return _skip("page_idle_targets_remain")
            instance_payload = _fresh_instance_payload(context)
            actor_id = instance_payload.get("actor_id")
            if not isinstance(actor_id, str) or not actor_id.strip():
                actor_id = local_actor["actor_id"]
            endpoint = _browser_endpoint(instance_payload)
            if endpoint is None:
                return _skip("browser_port_missing")
            if _has_real_user_page(endpoint):
                return _skip("real_user_page_present")
```

Do not add retry scheduling in this task.

- [ ] **Step 3: Run release handler tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_page_expired_handler.py::BrowserReleaseHandlerTests::test_release_logs_skip_reason_when_real_user_page_exists \
  tests/test_browser_page_expired_handler.py::BrowserReleaseHandlerTests::test_release_noops_when_parent_turn_running \
  tests/test_browser_page_expired_handler.py::BrowserReleaseHandlerTests::test_release_noops_when_page_idle_targets_remain \
  tests/test_browser_page_expired_handler.py::BrowserReleaseHandlerTests::test_release_invokes_launcher_after_rechecks_pass
```

Expected after implementation: PASS.

### Task 6: End-to-end and residue verification

**Files:**

- Test-only verification.

- [ ] **Step 1: Run the resource lifecycle focused suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_active_instance_clears_browser_runtime_state \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_active_instance_stops_service_broker_browser_and_marks_inactive \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_release_cleans_owned_runtime_state \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_release_clears_foreign_endpoint_port_without_killing_foreign \
  tests/test_browser_page_expired_handler.py \
  tests/test_browser_lazy_release_integration.py::BrowserLazyReleaseIntegrationTests::test_lazy_runtime_releases_after_idle_and_restarts_on_next_browser_call
```

Expected: PASS.

- [ ] **Step 2: Run search/browser boundary suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_search_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_live_browser_guidance_is_cockpit_first \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_market_skills_use_native_browser_entry
```

Expected: PASS.

- [ ] **Step 3: Run scoped search residue scan**

Run:

```bash
rg -n '_ensure_browser_runtime|_browser_endpoint|_reload_instance_payload|_open_browser_page|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|cdp_background_page\.py|Target\.createTarget|refresh_page_idle\(|close_page_target\(|evaluate_page_open_gate\(' scripts/env/tools/search/_impl.py
```

Expected: no matches and exit code `1`.

- [ ] **Step 4: Run live surface residue scan**

Run:

```bash
rg -n 'Start discovery from native `search__open_browser`|use native `search__open_browser` with a focused query, then continue discovery|Use search\.open_browser for browser-native discovery|Call search\.open_browser to open the target in the instance browser' \
  tools/launcher/assets/roles framework/contracts buddyswitch/skills/market scripts/env/tools/search
```

Expected: no matches and exit code `1`.

- [ ] **Step 5: Run process residual checks**

Run:

```bash
ps -axo pid,ppid,pgid,command | rg 'fake_chrome_server|fake_browser_ensure|chrome_devtools_cockpit_proxy.py --upstream-command .*fea-tool' || true
lsof -nP -iTCP:9222 -sTCP:LISTEN || true
```

Expected:

- no `fake_chrome_server` or `fake_browser_ensure` residue;
- no `chrome_devtools_cockpit_proxy.py` residue whose command line points at this `fea-tool` worktree;
- `9222` may still have no listener; host `chrome-devtools-mcp@latest` wrappers are not failure evidence unless they are actor-owned by this worktree.

- [ ] **Step 6: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

## Acceptance Criteria

The implementation is accepted only when all of these are true:

- `instance stop` clears actor-owned upstream markers, Chrome marker, page idle state, and browser port.
- `env browser release` reuses the same cleanup path for owned/inactive endpoints.
- Foreign or host browser resources are not killed by actor cleanup.
- `env browser ensure` failure kills the Chrome PID it just launched.
- `list_pages` with no tracked pages schedules `browser.cockpit.release`.
- `list_pages` with tracked pages does not schedule release.
- `release` no-op due to a real user page emits an explicit skip reason and does not retry.
- `search.open_browser` contains no standalone browser ensure/open/TTL/cleanup code.
- Live roles, skills, and contracts remain cockpit-first.
- Focused and boundary test suites pass.
- Residual process checks return to baseline for actor-owned fake/runtime processes.

## Completion Report Requirements

After implementation, the final report must state:

- changed files and the lifecycle responsibility each file now owns;
- focused pytest command lines and exact pass/fail result lines;
- search residue scan command and exact no-match result;
- live surface residue scan command and exact no-match result;
- process residual check commands and whether actor-owned fake/runtime processes returned to baseline;
- `git diff --check` result;
- remaining risk that host Codex `chrome-devtools-mcp` processes are outside BuddySwitch actor scope.
