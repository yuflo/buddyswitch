# Launcher JSON Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation, then use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Web API parsing of launcher human output with an explicit launcher JSON contract for the existing Web-managed instance commands.

**Architecture:** Keep the browser-facing Web API unchanged. Add opt-in `--json` output to the existing launcher commands, then update `tools/launcher/web_management.py` to consume only those JSON outputs while leaving instance lifecycle truth in `buddyswitch-codex` and `tools/launcher/instance.sh`.

**Tech Stack:** Bash launcher, Python standard library JSON/subprocess/HTTP server, existing app-server helper, vanilla JavaScript UI, pytest/unittest, Node built-in assert.

---

## Scope

Implement the full cleanup described in:

```text
docs/spec/2026-05-24-launcher-json-contract-objective.md
docs/spec/2026-05-24-launcher-json-contract-test-plan.md
```

This is a cleanup of the Web-to-launcher boundary. It is not a new product
surface and not a second lifecycle implementation.

## Files To Modify

```text
scripts/env_manifest.py
tools/launcher/instance.sh
buddyswitch-codex
tools/launcher/web_management.py
tests/test_buddyswitch_launcher.py
tests/test_web_management.py
```

`buddyswitch-codex` may only need help text updates for `--json` examples if
the top-level help should advertise them. Do not restructure the top-level
dispatcher.

## Files Expected To Stay Behaviorally Unchanged

```text
tools/launcher/app_server.py
tools/launcher/app_server.sh
tools/launcher/assets/web-management/index.html
tools/launcher/assets/web-management/styles.css
tools/launcher/assets/web-management/app.js
tests/web_management_ui_state.test.js
```

Only touch these files if a focused test exposes a real mismatch with the JSON
contract. The UI should not need changes because browser-facing HTTP responses
stay stable.

## Global Implementation Rules

- Keep human CLI output unchanged unless `--json` is passed.
- Do not add a generic SDK, proxy layer, command registry, queue, framework, or
  plugin system.
- Do not make Web dynamically expose every launcher command.
- Do not keep a long-lived Web fallback that parses old text output.
- Do not directly edit `buddyswitch/objects/**` or
  `buddyswitch/local/buddybox/**`.
- Do not use `shell=True`.
- Preserve existing exit codes: `2` invalid request, `3` lifecycle block.
- Use `json.dumps(..., ensure_ascii=True)` from Python for generated JSON.

## Task 1: Add Launcher JSON Tests For Read-Only Commands

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing test for `instance buddies --json`**

Add a test near the current buddies test:

```python
def test_instance_buddies_json_is_structured_and_read_only(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        source_home_path = Path(source_home)
        shared_root = source_home_path / ".codex-buddyswitch"
        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)

        completed = subprocess.run(
            [str(LAUNCHER), "instance", "buddies", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        buddy_ids = {row["id"] for row in payload["buddies"]}
        self.assertIn("pm", buddy_ids)
        self.assertIn("dev", buddy_ids)
        self.assertIn("market", buddy_ids)
        for row in payload["buddies"]:
            self.assertIsInstance(row["id"], str)
            self.assertIsInstance(row["label"], str)
            self.assertIsInstance(row["scope"], str)
        self.assertFalse(shared_root.exists(), "instance buddies --json must not create runtime state")
```

- [ ] **Step 2: Add failing test for empty `instance list --json`**

Add:

```python
def test_instance_list_json_empty_returns_empty_array(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        env = os.environ.copy()
        env["HOME"] = str(Path(source_home))
        env.pop("CODEX_HOME", None)

        completed = subprocess.run(
            [str(LAUNCHER), "instance", "list", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"instances": []})
        self.assertNotIn("No BuddySwitch instances found.", completed.stdout)
```

- [ ] **Step 3: Add failing test for filtered `instance list --json`**

Add:

```python
def test_instance_list_json_filters_by_buddy(self) -> None:
    with tempfile.TemporaryDirectory() as source_home:
        source_home_path = Path(source_home)
        shared_root = source_home_path / ".codex-buddyswitch"
        for instance_id, buddy in (
            ("inst-pm-a", "pm"),
            ("inst-dev-b", "dev"),
        ):
            instance_root = shared_root / "instances" / instance_id
            instance_root.mkdir(parents=True, exist_ok=True)
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "buddy": buddy,
                        "status": "inactive",
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
            [str(LAUNCHER), "instance", "list", "--json", "--buddy", "pm"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(len(payload["instances"]), 1)
        row = payload["instances"][0]
        self.assertEqual(row["instance_id"], "inst-pm-a")
        self.assertEqual(row["buddy"], "pm")
        self.assertEqual(row["status"], "inactive")
        self.assertEqual(row["app_server_health"], "unhealthy")
        self.assertIsNone(row["thread_id"])
        self.assertIsNone(row["browser_port"])
```

- [ ] **Step 4: Run tests and verify they fail for missing `--json` support**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'buddies_json or list_json' -q
```

Expected: FAIL because `instance buddies` and `instance list` do not yet accept
`--json`.

## Task 2: Implement Read-Only Launcher JSON Output

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `tools/launcher/instance.sh`

- [ ] **Step 1: Add `--json` option to `scripts/env_manifest.py list-buddies`**

Change `_cmd_list_buddies` so normal output stays TSV and `--json` returns:

```json
{"buddies":[{"id":"pm","label":"PM","scope":"..."}]}
```

Add parser support:

```python
cmd_list.add_argument("--json", action="store_true")
```

- [ ] **Step 2: Update `buddyswitch_instance_buddies` option parsing**

In `tools/launcher/instance.sh`, accept only:

```text
--json
help
-h
--help
```

For `--json`, call:

```bash
python3 "${REPO_ROOT}/scripts/env_manifest.py" list-buddies --json
```

For no options, keep:

```bash
python3 "${REPO_ROOT}/scripts/env_manifest.py" list-buddies
```

- [ ] **Step 3: Add `--json` parsing to `buddyswitch_instance_list`**

Extend the existing while-loop to accept `--json` in any position alongside
`--buddy <buddy>`.

When `--json` is absent, preserve the current human output exactly.

When `--json` is present:

- collect the same instance summaries as the current table path
- return `{"instances":[]}` for no matching rows
- return `app_server_health` as `"healthy"` or `"unhealthy"`
- return missing `thread_id` as JSON `null`
- return missing `browser_port` as JSON `null`

- [ ] **Step 4: Run focused read-only tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'buddies or list_json or instance_list_empty_points_to_start_buddy or instance_list_prints_stored_instances_and_filters_by_buddy' -q
```

Expected: PASS. Human list and buddies tests must still pass.

- [ ] **Step 5: Commit read-only JSON contract**

```bash
git add scripts/env_manifest.py tools/launcher/instance.sh tests/test_buddyswitch_launcher.py
git commit -m "Add JSON output for read-only instance commands"
```

## Task 3: Add Launcher JSON Tests For Mutating Commands

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing test for `instance start --json`**

Use the same fake Codex/browser setup as the existing service-mode start tests.
Run:

```python
[str(LAUNCHER), "instance", "start", "--buddy", "pm", "--json"]
```

Assert:

```python
payload = json.loads(completed.stdout)
self.assertTrue(payload["instance_id"].startswith("inst-pm-"))
self.assertEqual(payload["buddy"], "pm")
self.assertTrue(payload["workspace_dir"].endswith("/workspace"))
self.assertTrue(payload["project_workspace_dir"].endswith("/project/workspace"))
self.assertTrue(payload["instance_record"].endswith("/instance.json"))
self.assertNotIn("Input: ./buddyswitch-codex", completed.stdout)
```

- [ ] **Step 2: Add failing test for `instance input --json`**

Use `_start_service_instance`. Run:

```python
[
    str(LAUNCHER),
    "instance",
    "input",
    ctx["instance_id"],
    "--text",
    "Advance the brief",
    "--json",
]
```

Assert:

```python
payload = json.loads(input_result.stdout)
self.assertEqual(payload["instance_id"], ctx["instance_id"])
self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
self.assertIn(payload["action"], {"start", "steer"})
self.assertIsInstance(payload["turn_id"], str)
self.assertNotIn("Started turn:", input_result.stdout)
self.assertNotIn("Steered turn:", input_result.stdout)
```

- [ ] **Step 3: Add failing test for `instance interrupt --json`**

Use active-turn fake state. Run:

```python
[
    str(LAUNCHER),
    "instance",
    "interrupt",
    ctx["instance_id"],
    "--json",
]
```

Assert:

```python
payload = json.loads(interrupt_result.stdout)
self.assertEqual(payload["instance_id"], ctx["instance_id"])
self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
self.assertEqual(payload["turn_id"], "turn-123")
```

Also keep the existing RPC assertions for `thread/turns/list` and
`turn/interrupt`.

- [ ] **Step 4: Add failing test for `instance stop --json`**

Use an active service instance. Run:

```python
[str(LAUNCHER), "instance", "stop", ctx["instance_id"], "--json"]
```

Assert:

```python
payload = json.loads(stop_result.stdout)
self.assertEqual(payload, {"instance_id": ctx["instance_id"], "status": "inactive"})
```

Keep the existing runtime cleanup assertions.

- [ ] **Step 5: Add failing test for `instance delete --json`**

Use an inactive target instance. Run:

```python
[str(LAUNCHER), "instance", "delete", "inst-pm-delete", "--yes", "--json"]
```

Assert:

```python
payload = json.loads(delete_result.stdout)
self.assertEqual(payload, {"instance_id": "inst-pm-delete", "deleted": True})
```

Keep existing assertions that target root is removed, other root remains, shared
state remains, and target worktree registration is removed.

- [ ] **Step 6: Run tests and verify they fail for missing mutating `--json` support**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy or input_ or interrupt_ or stop_ or instance_delete_removes_only_target_instance_without_shared_state' -q
```

Expected: FAIL for the new JSON test paths.

## Task 4: Implement Mutating Launcher JSON Output

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`

- [ ] **Step 1: Update help text**

Show JSON support for instance commands in `buddyswitch-codex` and
`tools/launcher/instance.sh` help text:

```text
buddyswitch-codex instance buddies [--json]
buddyswitch-codex instance start --buddy <buddy> [--json]
buddyswitch-codex instance input <instance-id> --text <text> [--json]
buddyswitch-codex instance stop <instance-id> [--json]
buddyswitch-codex instance interrupt <instance-id> [--json]
buddyswitch-codex instance list [--buddy <buddy>] [--json]
buddyswitch-codex instance delete <instance-id> [--yes] [--json]
```

- [ ] **Step 2: Add `--json` parsing to `start_codex`**

Allow `--json` after the buddy option. Preserve all current validation:

- missing buddy returns `2`
- unknown buddy returns existing validation failure
- unexpected extra args return `2`

After the locked bootstrap succeeds:

- human mode prints the existing lines unchanged
- JSON mode prints only the start JSON object

- [ ] **Step 3: Add `--json` parsing to `instance_input`**

Accept `--json` alongside `--text <text>`.

The underlying `buddyswitch_app_server_input` already returns JSON. In JSON mode,
normalize it by adding `instance_id` and `thread_id`, then print JSON.

In human mode, keep existing `Started turn:` / `Steered turn:` output.

- [ ] **Step 4: Add `--json` parsing to `instance_interrupt`**

Accept `--json` with no other behavior changes.

The underlying `buddyswitch_app_server_interrupt` already returns JSON. In JSON
mode, normalize it by adding `instance_id` and `thread_id`, then print JSON.

In human mode, keep existing `Interrupted turn:` output.

- [ ] **Step 5: Add `--json` parsing to `instance_stop`**

Accept `--json`.

After the existing runtime-lock stop succeeds:

- human mode prints `Instance stopped: <id>`
- JSON mode prints `{"instance_id":"<id>","status":"inactive"}`

- [ ] **Step 6: Add `--json` parsing to `instance_delete`**

Accept `--json` alongside `--yes`.

For confirmed delete:

- human mode preserves existing delete output from the locked command
- JSON mode must return only `{"instance_id":"<id>","deleted":true}` on stdout

Implementation detail: the locked delete path currently prints
`Instance deleted: <id>`. In JSON mode, suppress or capture that human stdout in
the wrapper and print the JSON object after success. Do not hide stderr from
failure paths.

Delete preview without `--yes` can remain human-only. If `--json` is passed
without `--yes`, return the existing preview or a clear invalid request; Web
does not call that path. Pick the smaller implementation and cover it only if
the code path is changed.

- [ ] **Step 7: Run mutating launcher tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy or input_ or interrupt_ or stop_ or instance_delete_removes_only_target_instance_without_shared_state' -q
```

Expected: PASS.

- [ ] **Step 8: Commit mutating JSON contract**

```bash
git add buddyswitch-codex tools/launcher/instance.sh tests/test_buddyswitch_launcher.py
git commit -m "Add JSON output for instance lifecycle commands"
```

## Task 5: Convert Web API Tests To JSON Boundary

**Files:**

- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Remove parser unit tests**

Delete tests for:

```text
test_parse_buddies_tsv_returns_expected_rows
test_parse_instance_list_handles_empty_and_rows
test_parse_start_and_turn_output
```

- [ ] **Step 2: Update fake runner calls for buddies and list**

Change expected commands:

```python
["instance", "buddies", "--json"]
["instance", "list", "--json"]
```

Use JSON stdout fixtures:

```python
json.dumps({"buddies": [{"id": "pm", "label": "PM", "scope": "Own product iteration and track progression."}]})
json.dumps({"instances": []})
```

- [ ] **Step 3: Update fake runner calls for create**

Change expected commands:

```python
["instance", "buddies", "--json"]
["instance", "start", "--buddy", "pm", "--json"]
["instance", "status", "inst-pm-demo", "--json"]
```

Use start stdout:

```python
json.dumps(
    {
        "instance_id": "inst-pm-demo",
        "buddy": "pm",
        "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
        "project_workspace_dir": "/tmp/shared/project/workspace",
        "instance_record": "/tmp/shared/instances/inst-pm-demo/instance.json",
    },
    ensure_ascii=True,
)
```

- [ ] **Step 4: Update fake runner calls for input**

Change expected command:

```python
["instance", "input", "inst-pm-demo", "--text", "Advance the brief", "--json"]
```

Use input stdout:

```python
json.dumps(
    {
        "instance_id": "inst-pm-demo",
        "thread_id": "thread-demo",
        "action": "start",
        "turn_id": "turn-demo",
    },
    ensure_ascii=True,
)
```

- [ ] **Step 5: Update fake runner calls for interrupt**

Change expected command:

```python
["instance", "interrupt", "inst-pm-demo", "--json"]
```

Use interrupt stdout:

```python
json.dumps(
    {
        "instance_id": "inst-pm-demo",
        "thread_id": "thread-demo",
        "turn_id": "turn-demo",
    },
    ensure_ascii=True,
)
```

- [ ] **Step 6: Update fake runner calls for stop and delete**

Change expected commands:

```python
["instance", "stop", "inst-pm-demo", "--json"]
["instance", "delete", "inst-pm-demo", "--yes", "--json"]
```

Use JSON stdout:

```python
json.dumps({"instance_id": "inst-pm-demo", "status": "inactive"}, ensure_ascii=True)
json.dumps({"instance_id": "inst-pm-demo", "deleted": True}, ensure_ascii=True)
```

- [ ] **Step 7: Add malformed launcher JSON tests**

Add a test for malformed buddies JSON:

```python
def test_buddies_route_maps_malformed_launcher_json_to_502(self) -> None:
    runner = FakeRunner()
    runner.add(
        ["instance", "buddies", "--json"],
        WEB_MANAGEMENT.CommandResult(returncode=0, stdout="pm\tPM\told\n", stderr="", timed_out=False),
    )
    _, base_url = self._start_server(runner)
    status, payload = self._request_json(base_url, method="GET", path="/api/buddies")
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")
```

Add a similar test for malformed start JSON after buddy validation succeeds.

- [ ] **Step 8: Run Web tests and verify they fail before Web implementation**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: FAIL because `tools/launcher/web_management.py` still calls old
commands and parser helpers.

## Task 6: Convert Web API Implementation To JSON Boundary

**Files:**

- Modify: `tools/launcher/web_management.py`

- [ ] **Step 1: Remove text parser helpers**

Delete:

```text
parse_buddies_tsv
parse_instance_list_tsv
parse_started_instance_id
parse_turn_action_output
parse_interrupt_turn_id
_split_tsv_line
```

- [ ] **Step 2: Add `_run_json_command` helper**

Add a helper on `WebManagementService`:

```python
def _run_json_command(self, args: list[str], *, timeout_seconds: float) -> dict[str, Any]:
    result = self._run_command(args, timeout_seconds=timeout_seconds)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HttpError(
            status=502,
            code="COMMAND_FAILED",
            message=f"Invalid JSON from launcher command: {' '.join(args)}",
        ) from exc
    if not isinstance(payload, dict):
        raise HttpError(
            status=502,
            code="COMMAND_FAILED",
            message=f"Invalid JSON object from launcher command: {' '.join(args)}",
        )
    return payload
```

- [ ] **Step 3: Update read routes**

Change:

```python
_list_buddies -> self._run_json_command(["instance", "buddies", "--json"], timeout_seconds=10)["buddies"]
_list_instances -> self._run_json_command(["instance", "list", "--json"], timeout_seconds=10)["instances"]
_get_instance_status -> self._run_json_command(["instance", "status", instance_id, "--json"], timeout_seconds=10)
```

If `buddies` or `instances` is missing or not a list, raise
`502 COMMAND_FAILED`.

- [ ] **Step 4: Update create**

Change start command to:

```python
payload = self._run_json_command(["instance", "start", "--buddy", buddy, "--json"], timeout_seconds=120)
instance_id = payload.get("instance_id")
```

Require `instance_id` to be a string and pass `validate_instance_id(instance_id)`
before status refresh.

- [ ] **Step 5: Update input**

Change input command to:

```python
payload = self._run_json_command(
    ["instance", "input", instance_id, "--text", text, "--json"],
    timeout_seconds=60,
)
response = {"ok": True, "instance": self._get_instance_status(instance_id)}
```

Copy only safe optional keys from launcher JSON into the HTTP response:

```text
action
turn_id
expected_turn_id
thread_id
```

- [ ] **Step 6: Update interrupt**

Change interrupt command to:

```python
payload = self._run_json_command(["instance", "interrupt", instance_id, "--json"], timeout_seconds=30)
```

Copy `turn_id` and `thread_id` if present, then refresh status.

- [ ] **Step 7: Update stop and delete**

Change commands:

```python
["instance", "stop", instance_id, "--json"]
["instance", "delete", instance_id, "--yes", "--json"]
```

Stop still returns refreshed status. Delete still returns:

```python
{"ok": True, "instance_id": instance_id}
```

- [ ] **Step 8: Run Web tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Web JSON consumption**

```bash
git add tools/launcher/web_management.py tests/test_web_management.py
git commit -m "Use launcher JSON contract in web management API"
```

## Task 7: Focused Regression Gates

**Files:**

- No planned file edits.

- [ ] **Step 1: Run Web and UI tests**

```bash
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
```

Expected: PASS.

- [ ] **Step 2: Run app-server client tests**

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected: PASS.

- [ ] **Step 3: Run service-mode launcher gate**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
```

Expected: PASS.

- [ ] **Step 4: Run lifecycle safety gate**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
```

Expected: PASS.

- [ ] **Step 5: Run browser cockpit and cleanup gate**

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Expected: PASS.

## Task 8: Manual Smoke

**Files:**

- No planned file edits unless smoke finds a real bug.

- [ ] **Step 1: Start the Web server**

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Expected stdout:

```text
BuddySwitch web management listening on http://127.0.0.1:8765
```

- [ ] **Step 2: Verify local API**

In another shell:

```bash
python3 - <<'PY'
import json
from urllib.request import urlopen

for path in ("/api/health", "/api/buddies", "/api/instances"):
    with urlopen("http://127.0.0.1:8765" + path, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
        print(path, response.status, payload.get("ok"))
PY
```

Expected:

```text
/api/health 200 True
/api/buddies 200 True
/api/instances 200 True
```

- [ ] **Step 3: Browser smoke**

Open:

```text
http://127.0.0.1:8765/
```

Expected:

- page loads
- status shows API ready
- buddy selector is populated
- instance list loads
- no console error from missing static assets

Do not create/delete real product instances during smoke unless explicitly
approved for the local machine state.

## Task 9: Full Verification And Review

**Files:**

- No planned file edits unless verification finds a real bug.

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run cleanup audits**

```bash
rg -n 'parse_buddies_tsv|parse_instance_list_tsv|parse_started_instance_id|parse_turn_action_output|parse_interrupt_turn_id' tools/launcher/web_management.py tests/test_web_management.py
rg -n 'buddyswitch/objects|buddyswitch/local/buddybox' tools/launcher/web_management.py tools/launcher/instance.sh tests/test_web_management.py tests/test_buddyswitch_launcher.py
rg -n 'shell=True|FastAPI|Flask|aiohttp|queue|workflow|plugin|auth' tools/launcher/web_management.py tools/launcher/instance.sh
```

Expected:

- first command has no matches
- forbidden runtime paths are not write targets in changed code
- no new framework, queue, workflow, plugin, or auth system appears

- [ ] **Step 3: Review diff**

```bash
git diff --stat
git diff
git status --short --branch
```

Review must confirm:

- changes are limited to launcher JSON contract, Web JSON consumption, tests,
  and necessary help text
- Web layer only wraps existing CLI commands
- lifecycle truth is not copied into Web Python
- human CLI output remains covered
- tests were not skipped or weakened
- no direct runtime object or buddybox writes were added
- UI remains a clear management interface and not a new dashboard or landing page

- [ ] **Step 4: Final commit if needed**

If earlier commits were not made per task, commit the complete verified change:

```bash
git add scripts/env_manifest.py tools/launcher/instance.sh buddyswitch-codex tools/launcher/web_management.py tests/test_buddyswitch_launcher.py tests/test_web_management.py
git commit -m "Use launcher JSON contract for web management"
```

## Handoff Notes

The intended final state is intentionally small:

- launcher gains opt-in JSON for the commands Web already uses
- Web consumes those JSON commands
- old Web text parsers are gone
- browser-facing API stays stable
- service-mode lifecycle remains the only source of truth

Do not expand the task into a generic local API platform.
