# Multi-Instance Runtime Checkpoint Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after human confirmation. Use `superpowers:subagent-driven-development` only if the human explicitly authorizes subagents. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two known pre-submit blockers so the multi-instance Buddy runtime worktree can be committed as a clean checkpoint.

**Architecture:** Keep the change narrow. Active market/browser docs must describe the new instance-bound cockpit tokens already used by runtime metadata, and `/api/workspace` snapshot reads must fail closed when a configured runtime lock cannot be acquired. Do not add compatibility layers, alternate browser aliases, or a broader locking framework.

**Tech Stack:** Markdown contract docs, Python runtime projection code, `unittest`, `pytest`, `rg`, `git diff --check`.

---

## Status

- Draft plan only.
- Do not edit implementation files before human confirmation.
- Do all work in `/Users/chen/Dev/buddyswitch/.worktrees/multi-instance-buddy-runtime-architecture`.
- Do not edit `/Users/chen/Dev/buddyswitch` main checkout.
- Do not commit until fixes pass verification and the human confirms the checkpoint commit.

## Preflight Gate

### Target Outcome And Current Bottleneck

The current bottleneck is not feature implementation. The implementation has already passed the full local suite, but the branch still has two known review blockers before a defensible checkpoint commit:

1. Active market/browser contract docs still mention `shared-browser` and `shared-cockpit`.
2. `runtime_snapshot_lock()` can time out on a busy lock and continue reading without the lock.

The target outcome is a verified checkpoint where active docs, runtime behavior, and tests agree on the multi-instance contract.

### Confirmed Facts

- Main checkout is clean: `git status --short --branch` in `/Users/chen/Dev/buddyswitch` returned `## main...origin/main`.
- Isolated worktree is active: `git status --short --branch` in `/Users/chen/Dev/buddyswitch/.worktrees/multi-instance-buddy-runtime-architecture` returned branch `docs/multi-instance-buddy-runtime-architecture` with expected uncommitted runtime changes.
- Active docs still contain old tokens:
  - `framework/contracts/market.md` contains `shared-browser` at the Must Do and Browser Cockpit Rules sections.
  - `framework/docs/browser-cockpit.md` contains `shared-browser` and `shared-cockpit` in shared host execution metadata and runtime rules.
- Runtime metadata already expects the new tokens:
  - `tests/test_repo_consistency.py` defines `BROWSER_COCKPIT_METADATA["browser_profile"] == "instance-browser"`.
  - `tests/test_repo_consistency.py` defines `BROWSER_COCKPIT_METADATA["session_continuity"] == "instance-cockpit"`.
- `scripts/runtime_store/projections.py::runtime_snapshot_lock()` currently breaks out of the retry loop after timeout and then yields without `locked == True`.

### Assumptions To Confirm

- When `BUDDYSWITCH_SHARED_ROOT` is set, a busy, unavailable, or unsupported runtime snapshot lock should fail closed internally, while `/api/workspace` reports a clear temporary busy response and the console keeps showing the last loaded workspace data.
- When `BUDDYSWITCH_SHARED_ROOT` is not set, local projection reads may keep the current no-lock behavior so source-checkout tests and local inspection remain usable.
- Legacy planning docs under `docs/dev1626/**` may continue to mention `shared-browser` because `tests/test_repo_consistency.py::test_dev1626_active_plans_define_browser_cockpit_happy_path` intentionally asserts that historical text.

### Tools And Boundaries

- Use only the isolated worktree path for edits:
  - `/Users/chen/Dev/buddyswitch/.worktrees/multi-instance-buddy-runtime-architecture`
- Verify main remains clean before the final report:
  - `git -C /Users/chen/Dev/buddyswitch status --short --branch`
- Do not run destructive git commands.
- Do not stage or commit until implementation verification passes.

### Verification Plan

Run targeted tests after each task, then run full verification before proposing the checkpoint commit:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_market_active_contract_docs_require_browser_native_wording -q
python3 -m pytest tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_uses_runtime_lock_when_shared_root_is_available tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_fails_closed_when_runtime_lock_is_busy tests/test_switch_runtime.py::ContextPanelServerTests::test_workspace_api_returns_busy_json_when_snapshot_lock_is_busy tests/test_console_app_contract.py::ConsoleAppContractTests::test_refresh_workspace_busy_keeps_existing_data_and_status -q
python3 -m pytest -q
git diff --check
git status --short --branch
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

Stop condition: all commands pass, active docs have no `shared-browser` or `shared-cockpit` tokens, and main checkout remains clean.

## File Map

- Modify `framework/contracts/market.md`: replace active browser profile/session continuity wording with instance-bound terms while preserving the selected-skill market contract.
- Modify `framework/docs/browser-cockpit.md`: replace shared host execution metadata and runtime wording with `instance-browser` and `instance-cockpit`.
- Modify `tests/test_repo_consistency.py`: add a regression assertion that active market contract docs do not use legacy browser cockpit tokens.
- Modify `scripts/runtime_store/projections.py`: make configured runtime snapshot lock acquisition fail closed on lock open/acquire/support failure.
- Modify `scripts/serve_context_panel.py`: translate snapshot lock contention into a `503` JSON busy response.
- Modify `framework/console/app.js`: preserve existing rendered data when the workspace API returns busy, and show a short retry-later status.
- Modify `tests/test_switch_runtime.py`: add regression tests for busy configured runtime locks and `/api/workspace` busy responses.
- Modify `tests/test_console_app_contract.py`: add a Node harness regression test for the console busy-refresh UX.

## Non-Goals

- Do not redesign the browser cockpit contract.
- Do not rename the `market-browser-native` tool scope.
- Do not remove historical references in archived or superseded planning docs.
- Do not add aliases from `shared-browser` to `instance-browser`.
- Do not change launcher/browser instance lifecycle beyond the snapshot lock behavior.

## Task 1: Lock Active Docs To Instance Cockpit Tokens

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `framework/contracts/market.md`
- Modify: `framework/docs/browser-cockpit.md`

- [ ] **Step 1: Write the failing active-doc regression test**

In `tests/test_repo_consistency.py`, extend `test_market_active_contract_docs_require_browser_native_wording` so active docs reject legacy cockpit tokens:

```python
    def test_market_active_contract_docs_require_browser_native_wording(self) -> None:
        required_tokens = ("chrome-devtools-cockpit", "browser-native", "user-approved")
        forbidden_tokens = ("search-assist", "shared-browser", "shared-cockpit")

        for path in ACTIVE_MARKET_CONTRACT_DOCS:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in required_tokens:
                    self.assertIn(token, text, msg=f"{path.relative_to(ROOT)} missing required token '{token}'")
                for token in forbidden_tokens:
                    self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} must not include '{token}'")
```

- [ ] **Step 2: Run the targeted test and confirm it fails for the known docs**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_market_active_contract_docs_require_browser_native_wording -q
```

Expected result before docs are fixed:

```text
FAILED tests/test_repo_consistency.py::RepoConsistencyTests::test_market_active_contract_docs_require_browser_native_wording
```

The failure must point at `framework/contracts/market.md` or `framework/docs/browser-cockpit.md` containing `shared-browser` or `shared-cockpit`.

- [ ] **Step 3: Update `framework/contracts/market.md` active wording**

Make these exact semantic replacements:

```text
Use browser profile `shared-browser` with session continuity across market runs.
```

Replace with:

```text
Use browser profile `instance-browser` with `instance-cockpit` session continuity inside the active Buddy instance.
```

```text
The cockpit must run headed (`browser_mode=headed-only`) and use profile `shared-browser`.
```

Replace with:

```text
The cockpit must run headed (`browser_mode=headed-only`) and use profile `instance-browser` with `session_continuity=instance-cockpit`.
```

Keep `chrome-devtools-cockpit`, `browser-native`, `mandatory-takeover`, `no-silent-degrade`, and `user-approved` wording intact.

- [ ] **Step 4: Update `framework/docs/browser-cockpit.md` active metadata**

Replace the shared host execution metadata block with:

```markdown
- `execution_mode = "browser-cockpit-native"`
- `browser_mode = "headed-only"`
- `browser_profile = "instance-browser"`
- `browser_executor = "chrome-devtools-cockpit"`
- `discovery_mode = "browser-native"`
- `login_policy = "mandatory-takeover"`
- `fallback_policy = "no-silent-degrade"`
- `session_continuity = "instance-cockpit"`
- `evidence_capture_level = "medium"`
```

Replace the first runtime rule sentence:

```text
All six skills run in one shared headed cockpit profile (`shared-browser`) with session continuity (`shared-cockpit`) through `chrome-devtools-cockpit`.
```

With:

```text
All six skills use one instance-bound headed cockpit profile (`instance-browser`) with session continuity (`instance-cockpit`) through `chrome-devtools-cockpit` for the active Buddy instance.
```

- [ ] **Step 5: Run targeted docs tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_market_active_contract_docs_require_browser_native_wording tests/test_repo_consistency.py::RepoConsistencyTests::test_market_skill_metadata_uses_instance_cockpit_tokens tests/test_repo_consistency.py::RepoConsistencyTests::test_market_cockpit_doc_defines_resolve_context_execution_boundary -q
```

Expected result:

```text
3 passed
```

- [ ] **Step 6: Grep active docs for old tokens**

Run:

```bash
rg -n "shared-browser|shared-cockpit" framework/contracts/market.md framework/docs/browser-cockpit.md framework/docs/switch-spec.md framework/templates/research-report.md buddyswitch/skills/market
```

Expected result:

```text
no matches
```

If this command finds only historical files outside the active-doc paths above, do not edit those files in this task.

## Task 2: Show Temporary Busy State For Locked Workspace Refresh

**Files:**

- Modify: `tests/test_switch_runtime.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `scripts/serve_context_panel.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `framework/console/app.js`

- [ ] **Step 1: Write the failing busy-lock regression test**

Add this test to `WorkspaceProjectionFacadeTests` in `tests/test_switch_runtime.py`, directly after `test_workspace_projection_snapshot_uses_runtime_lock_when_shared_root_is_available`:

```python
    def test_workspace_projection_snapshot_fails_closed_when_runtime_lock_is_busy(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir_name:
            shared_root = Path(temp_dir_name).resolve() / ".codex-buddyswitch"
            shared_root.mkdir(parents=True)

            def busy_flock(_lock_fd: int, mode: int) -> None:
                if mode & workspace_projections.fcntl.LOCK_SH:
                    raise BlockingIOError("busy")

            with patch.dict(
                os.environ,
                {
                    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                    "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS": "0",
                },
                clear=False,
            ):
                with patch("runtime_store.projections.build_workspace_projection") as mock_build:
                    with patch("runtime_store.projections.fcntl.flock", side_effect=busy_flock):
                        with self.assertRaisesRegex(
                            workspace_projections.RuntimeSnapshotLockError,
                            "could not acquire runtime snapshot lock",
                        ):
                            workspace_projections.build_workspace_projection_snapshot()

        mock_build.assert_not_called()
```

- [ ] **Step 2: Run the targeted test and confirm it fails before implementation**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_fails_closed_when_runtime_lock_is_busy -q
```

Expected result before implementation:

```text
FAILED tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_fails_closed_when_runtime_lock_is_busy
```

The failure should show that no `RuntimeSnapshotLockError` is raised and `build_workspace_projection()` is still called.

- [ ] **Step 3: Write the failing `/api/workspace` busy response test**

In `tests/test_switch_runtime.py`, add these imports near the existing imports:

```python
import threading
import urllib.error
import urllib.request
```

Add this import near the existing script imports:

```python
import serve_context_panel  # noqa: E402
```

Add this class after `WorkspaceProjectionFacadeTests`:

```python
class ContextPanelServerTests(unittest.TestCase):
    def test_workspace_api_returns_busy_json_when_snapshot_lock_is_busy(self) -> None:
        with patch(
            "serve_context_panel.build_workspace_projection_snapshot",
            side_effect=workspace_projections.RuntimeSnapshotLockError("busy"),
        ):
            server = serve_context_panel.ThreadingHTTPServer(
                ("127.0.0.1", 0),
                serve_context_panel.ContextPanelHandler,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/workspace"
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(url, timeout=2)
                self.assertEqual(raised.exception.code, 503)
                payload = json.loads(raised.exception.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "runtime_snapshot_busy")
        self.assertEqual(payload["message"], "Workspace is updating. Retry shortly.")
```

- [ ] **Step 4: Write the failing console busy-refresh UX test**

In `tests/test_console_app_contract.py`, add this test to `ConsoleAppContractTests`:

```python
    def test_refresh_workspace_busy_keeps_existing_data_and_status(self) -> None:
        script = textwrap.dedent(
            """
            const fs = require("fs");
            const vm = require("vm");

            function makeElement(tagName = "div") {
              return {
                tagName,
                children: [],
                className: "",
                textContent: "",
                type: "",
                disabled: false,
                dataset: {},
                append(...nodes) { this.children.push(...nodes); },
                appendChild(node) { this.children.push(node); return node; },
                replaceChildren(...nodes) { this.children = [...nodes]; },
                addEventListener() {},
                removeEventListener() {},
                setAttribute() {},
                classList: {
                  add() {},
                  remove() {},
                  toggle() {},
                  contains() { return false; },
                },
              };
            }

            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) {
                  elements.set(id, makeElement("div"));
                }
                return elements.get(id);
              },
              createElement(tag) {
                return makeElement(tag);
              },
            };

            const context = {
              console,
              window: {
                location: { protocol: "file:" },
                prompt() {},
              },
              document,
              navigator: {
                clipboard: {
                  writeText: async () => {},
                },
              },
              setTimeout() {},
              clearTimeout() {},
            };
            context.globalThis = context;
            vm.createContext(context);

            const source = fs.readFileSync(process.env.CONSOLE_APP_PATH, "utf8");
            vm.runInContext(
              source + "\\nglobalThis.__consoleContract = { applyWorkspaceData, refreshWorkspaceData, workspace: () => workspace, status: () => ({ text: dataStatus.textContent, state: dataStatus.dataset.state }) };\\n",
              context,
            );

            context.__consoleContract.applyWorkspaceData({
              generated_at: "existing-snapshot",
              tracks: [{ id: "track-existing", title: "Existing Track", task_ids: [] }],
              tasks: [],
              artifacts: [],
              run_audits: [],
            });
            context.window.location.protocol = "http:";
            context.fetch = async () => ({
              ok: false,
              status: 503,
              json: async () => ({
                ok: false,
                error: "runtime_snapshot_busy",
                message: "Workspace is updating. Retry shortly.",
              }),
            });

            (async () => {
              const refreshed = await context.__consoleContract.refreshWorkspaceData({ silent: true });
              process.stdout.write(JSON.stringify({
                refreshed,
                workspace: context.__consoleContract.workspace(),
                status: context.__consoleContract.status(),
              }));
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

        env = os.environ.copy()
        env.update({"CONSOLE_APP_PATH": str(CONSOLE_APP)})
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"node harness failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        result = json.loads(completed.stdout)

        self.assertFalse(result["refreshed"])
        self.assertEqual(result["workspace"]["generated_at"], "existing-snapshot")
        self.assertEqual(result["workspace"]["tracks"][0]["id"], "track-existing")
        self.assertEqual(result["status"]["text"], "Workspace is updating. Retry shortly.")
        self.assertEqual(result["status"]["state"], "warning")
```

- [ ] **Step 5: Run the API/UI tests and confirm they fail before implementation**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py::ContextPanelServerTests::test_workspace_api_returns_busy_json_when_snapshot_lock_is_busy tests/test_console_app_contract.py::ConsoleAppContractTests::test_refresh_workspace_busy_keeps_existing_data_and_status -q
```

Expected result before implementation:

```text
FAILED tests/test_switch_runtime.py::ContextPanelServerTests::test_workspace_api_returns_busy_json_when_snapshot_lock_is_busy
FAILED tests/test_console_app_contract.py::ConsoleAppContractTests::test_refresh_workspace_busy_keeps_existing_data_and_status
```

The first failure should show `/api/workspace` does not return a structured busy `503`. The second failure should show the console treats busy like a generic workspace read failure.

- [ ] **Step 6: Add an explicit runtime snapshot lock error**

In `scripts/runtime_store/projections.py`, add this class near the lock constants:

```python
class RuntimeSnapshotLockError(RuntimeError):
    """Raised when a configured runtime snapshot lock cannot protect a read."""
```

- [ ] **Step 7: Make configured lock failures fail closed**

Replace `runtime_snapshot_lock()` with this implementation:

```python
@contextmanager
def runtime_snapshot_lock() -> Any:
    lock_path = _runtime_lock_path()
    if lock_path is None:
        yield
        return
    if fcntl is None:
        raise RuntimeSnapshotLockError("runtime snapshot lock requires fcntl support")

    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise RuntimeSnapshotLockError(f"could not open runtime snapshot lock: {lock_path}") from exc

    locked = False
    timeout_seconds = _runtime_lock_timeout_seconds()
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeSnapshotLockError(f"could not acquire runtime snapshot lock: {lock_path}") from exc
                time.sleep(LOCK_WAIT_POLL_SECONDS)
        yield
    finally:
        if locked:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(lock_fd)
```

This preserves no-env local reads, but if `BUDDYSWITCH_SHARED_ROOT` configures a runtime lock then failing to protect the snapshot is an explicit error.

- [ ] **Step 8: Return structured busy JSON from `/api/workspace`**

In `scripts/serve_context_panel.py`, change the projection import to:

```python
from runtime_store.projections import RuntimeSnapshotLockError, build_workspace_projection_snapshot  # noqa: E402
```

Replace `send_workspace_json()` with:

```python
    def send_workspace_json(self, include_body: bool = True) -> None:
        status = 200
        headers: dict[str, str] = {}
        try:
            data = build_workspace_projection_snapshot()
        except RuntimeSnapshotLockError:
            status = 503
            headers["Retry-After"] = "1"
            data = {
                "ok": False,
                "error": "runtime_snapshot_busy",
                "message": "Workspace is updating. Retry shortly.",
            }

        body = json.dumps(data, ensure_ascii=True, indent=2).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if include_body:
            self.wfile.write(body)
```

- [ ] **Step 9: Preserve old console data on busy refresh**

In `framework/console/app.js`, add this helper above `refreshWorkspaceData()`:

```javascript
async function workspaceApiError(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
```

Then replace the non-ok response block inside `refreshWorkspaceData()`:

```javascript
    if (!response.ok) {
      throw new Error(`Workspace API returned ${response.status}`);
    }
```

With:

```javascript
    if (!response.ok) {
      const payload = await workspaceApiError(response);
      if (response.status === 503 && payload?.error === "runtime_snapshot_busy") {
        setDataStatus(payload.message || "Workspace is updating. Retry shortly.", "warning");
        return false;
      }
      throw new Error(`Workspace API returned ${response.status}`);
    }
```

Do not call `applyWorkspaceData()` on the busy path. This preserves the previously loaded workspace data.

- [ ] **Step 10: Run targeted lock/API/UI tests**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_uses_runtime_lock_when_shared_root_is_available tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests::test_workspace_projection_snapshot_fails_closed_when_runtime_lock_is_busy tests/test_switch_runtime.py::ContextPanelServerTests::test_workspace_api_returns_busy_json_when_snapshot_lock_is_busy tests/test_console_app_contract.py::ConsoleAppContractTests::test_refresh_workspace_busy_keeps_existing_data_and_status -q
```

Expected result:

```text
4 passed
```

## Task 3: Full Verification And Checkpoint Readiness

**Files:**

- Inspect only: entire worktree diff
- No new implementation changes unless verification identifies a direct blocker

- [ ] **Step 1: Run full Python suite**

Run:

```bash
python3 -m pytest -q
```

Expected result:

```text
287 passed
```

If the count changes only because new tests were added, accept the new higher count when all tests pass.

- [ ] **Step 2: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected result:

```text
no output
```

- [ ] **Step 3: Verify active docs do not contain legacy tokens**

Run:

```bash
rg -n "shared-browser|shared-cockpit" framework/contracts/market.md framework/docs/browser-cockpit.md framework/docs/switch-spec.md framework/templates/research-report.md buddyswitch/skills/market
```

Expected result:

```text
no matches
```

- [ ] **Step 4: Verify worktree and main checkout boundaries**

Run in the isolated worktree:

```bash
git status --short --branch
```

Expected result:

```text
## docs/multi-instance-buddy-runtime-architecture
```

The status should show only intended branch changes, including this plan document and the implementation/test/doc edits.

Run from anywhere:

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

Expected result:

```text
## main...origin/main
```

- [ ] **Step 5: Prepare checkpoint commit only after human confirmation**

If verification passes and the human confirms the commit, stage the complete checkpoint from the isolated worktree:

```bash
git add buddyswitch-codex buddyswitch/skills/market docs/spec_dev docs/whiteboard framework scripts tests tools/launcher
git status --short --branch
```

Then commit:

```bash
git commit -m "Implement multi-instance Buddy runtime checkpoint"
```

Do not commit from the main checkout.

## Self-Review Checklist

- The plan covers both known blockers from the review log.
- The docs task includes a failing regression test before changing docs.
- The lock task includes a failing regression test before changing runtime code.
- The verification commands prove active contract cleanup, runtime lock behavior, full test health, diff cleanliness, and main checkout isolation.
- The plan does not add speculative abstractions, compatibility aliases, or unrelated cleanup.
