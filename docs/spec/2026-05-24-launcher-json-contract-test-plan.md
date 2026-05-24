# Launcher JSON Contract Test Plan

Date: 2026-05-24

## Test Goal

Prove that the Web API consumes a stable launcher JSON contract instead of
parsing human CLI text, while preserving the current lifecycle behavior and
human CLI experience.

Tests must be requirement driven. They should verify user-facing and
integration boundaries, not private implementation details chosen only to make
the code pass.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `instance buddies --json` returns a JSON object with a `buddies` array and does not create runtime state. |
| FR2 | `instance buddies` without `--json` keeps the existing TSV human output. |
| FR3 | `instance list --json` returns `{"instances":[]}` when no instances exist. |
| FR4 | `instance list --json --buddy <buddy>` returns filtered instance summaries with the same data currently shown in the table output. |
| FR5 | `instance list` without `--json` keeps the existing human empty message and TSV table output. |
| FR6 | `instance start --buddy <buddy> --json` returns the created instance id, buddy id, workspace dir, project workspace dir, and instance record path. |
| FR7 | `instance start --buddy <buddy>` without `--json` keeps existing human hints. |
| FR8 | `instance input <id> --text <text> --json` returns `instance_id`, `thread_id`, `action`, and `turn_id`; it includes `expected_turn_id` when the app-server reports one. |
| FR9 | `instance input <id> --text <text>` without `--json` keeps existing `Started turn:` / `Steered turn:` output. |
| FR10 | `instance interrupt <id> --json` returns `instance_id`, `thread_id`, and `turn_id`. |
| FR11 | `instance interrupt <id>` without `--json` keeps existing `Interrupted turn:` output. |
| FR12 | `instance stop <id> --json` returns `instance_id` and `status: inactive`, while still stopping the app-server, runtime broker, and browser markers. |
| FR13 | `instance stop <id>` without `--json` keeps existing `Instance stopped:` output. |
| FR14 | `instance delete <id> --yes --json` returns `instance_id` and `deleted: true`, while preserving delete safety guards. |
| FR15 | `instance delete <id> --yes` without `--json` keeps existing `Instance deleted:` output. |
| FR16 | Existing failure exit codes and stderr messages remain stable for invalid requests and lifecycle blocks. |
| FR17 | The Web API calls launcher commands with `--json` for every route except health and status, where status already uses `--json`. |
| FR18 | The Web API rejects malformed launcher JSON with structured `502 COMMAND_FAILED` JSON, not stack traces. |
| FR19 | The Web API no longer exposes or tests TSV/text parser helpers. |
| FR20 | UI state behavior remains unchanged because browser-facing HTTP shapes stay unchanged. |
| FR21 | No test weakens lifecycle safety by mocking below the launcher boundary for service-mode behavior. |
| FR22 | No implementation directly edits `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | `tests/test_buddyswitch_launcher.py` subprocess test for `instance buddies --json`; assert parsed JSON and shared root absence. |
| FR2 | Existing buddies human-output test remains and continues to assert `pm`, `dev`, and `market` in stdout. |
| FR3 | New subprocess test for `instance list --json` with isolated empty HOME. |
| FR4 | New subprocess test with two stored instance records and `instance list --json --buddy pm`. |
| FR5 | Existing empty list and table/filter tests remain. |
| FR6 | New service-mode launcher test using the existing fake Codex/browser harness and `instance start --buddy pm --json`. |
| FR7 | Existing start tests that assert human command hints remain. |
| FR8 | New service-mode launcher test using the existing fake app-server state and `instance input <id> --text ... --json`. |
| FR9 | Existing input tests that assert human turn output remain. |
| FR10 | New service-mode launcher test using active-turn state and `instance interrupt <id> --json`. |
| FR11 | Existing interrupt active-turn test remains. |
| FR12 | Extend or add stop test that runs `instance stop <id> --json` and still asserts runtime cleanup. |
| FR13 | Existing stop human-output coverage remains or is added if missing. |
| FR14 | New delete test for inactive instance with `--yes --json`; existing active-delete block tests remain. |
| FR15 | Existing delete human-output test remains. |
| FR16 | Existing invalid id, missing target, active app-server, browser pid, browser endpoint, and worktree failure tests remain. |
| FR17 | Update `tests/test_web_management.py` fake runner expected calls to include `--json`. |
| FR18 | Add Web API tests where fake runner returns malformed stdout for `buddies --json`, `list --json`, and one mutating route. |
| FR19 | Remove parser unit tests for TSV and human text; add a code-review audit step using `rg`. |
| FR20 | Run `node tests/web_management_ui_state.test.js`; no UI helper changes expected. |
| FR21 | Keep service-mode tests at launcher subprocess boundary with fake external Codex/browser only. |
| FR22 | Final review plus `rg` audit for forbidden direct paths in changed files. |

## New And Updated Test Areas

### Launcher JSON Contract Tests

Modify:

```text
tests/test_buddyswitch_launcher.py
```

Add tests near the existing instance command tests.

#### 1. Buddies JSON Is Structured And Read Only

Command:

```bash
./buddyswitch-codex instance buddies --json
```

Expected:

- return code `0`
- stdout parses as JSON object
- `payload["buddies"]` is a non-empty list
- list contains buddy ids `pm`, `dev`, and `market`
- each row has string `id`, `label`, and `scope`
- isolated shared root was not created

#### 2. Empty List JSON Is Empty Array

Command:

```bash
./buddyswitch-codex instance list --json
```

With isolated HOME and no instance records.

Expected stdout:

```json
{"instances":[]}
```

No human empty-state text should appear in stdout when `--json` is passed.

#### 3. List JSON Filters By Buddy

Create two inactive test records under isolated shared root:

```text
inst-pm-a -> buddy pm
inst-dev-b -> buddy dev
```

Command:

```bash
./buddyswitch-codex instance list --json --buddy pm
```

Expected:

- return code `0`
- `payload["instances"]` contains one row
- row has `instance_id: inst-pm-a`
- row has `buddy: pm`
- row has `status: inactive`
- row has `app_server_health: unhealthy`
- row does not include `inst-dev-b`

#### 4. Start JSON Returns Created Instance Metadata

Use the existing fake Codex, fake browser, and auth bootstrap harness used by
service-mode start tests.

Command:

```bash
./buddyswitch-codex instance start --buddy pm --json
```

Expected:

- return code `0`
- stdout parses as JSON
- `instance_id` starts with `inst-pm-`
- `buddy` is `pm`
- `workspace_dir` points to the created instance workspace
- `project_workspace_dir` points to the shared project workspace
- `instance_record` points to the created `instance.json`
- stdout does not contain `Input: ./buddyswitch-codex`
- the created instance record still has active app-server metadata

#### 5. Input JSON Returns Action And Turn

Use an active service instance from `_start_service_instance`.

Command:

```bash
./buddyswitch-codex instance input <instance-id> --text "Advance the brief" --json
```

Expected:

- return code `0`
- stdout parses as JSON
- `instance_id` equals the target id
- `thread_id` equals the instance record thread id
- `action` is `start` or `steer` according to fake app-server state
- `turn_id` is a non-empty string
- human text `Started turn:` and `Steered turn:` is absent when `--json` is passed

#### 6. Interrupt JSON Returns Interrupted Turn

Use active-turn fake state.

Command:

```bash
./buddyswitch-codex instance interrupt <instance-id> --json
```

Expected:

- return code `0`
- stdout parses as JSON
- `instance_id` equals the target id
- `thread_id` equals the instance record thread id
- `turn_id` equals the active fake turn id
- fake RPC calls still include `thread/turns/list` and `turn/interrupt`

#### 7. Stop JSON Still Performs Full Cleanup

Use an active service instance.

Command:

```bash
./buddyswitch-codex instance stop <instance-id> --json
```

Expected:

- return code `0`
- stdout parses as `{"instance_id":"<id>","status":"inactive"}`
- stored instance record status is `inactive`
- app-server pid file is removed
- app-server socket marker is removed
- runtime broker pid/socket markers are removed
- browser pid marker is removed

#### 8. Delete JSON Still Preserves Safety

Use an inactive stored instance with a registered worktree.

Command:

```bash
./buddyswitch-codex instance delete <instance-id> --yes --json
```

Expected:

- return code `0`
- stdout parses as `{"instance_id":"<id>","deleted":true}`
- target instance root is removed
- unrelated instance root remains
- shared state remains
- registered target worktree is removed from `git worktree list --porcelain`

Existing active-delete block tests must keep using the real launcher path and
must still assert return code `3`.

### Web API Tests

Modify:

```text
tests/test_web_management.py
```

Replace TSV/text fixtures with JSON fixtures.

#### 1. Remove Web Parser Unit Tests

Remove tests that call:

```text
parse_buddies_tsv
parse_instance_list_tsv
parse_started_instance_id
parse_turn_action_output
parse_interrupt_turn_id
```

Those helpers should not exist after implementation.

#### 2. Add JSON Command Decode Unit Test

Exercise the Web service through HTTP with fake runner output that is not JSON.

Example for buddies:

```text
GET /api/buddies
runner stdout: "pm\tPM\told text\n"
```

Expected:

- HTTP status `502`
- `payload["ok"]` is `false`
- `payload["error"]["code"]` is `COMMAND_FAILED`
- error message says launcher output was invalid JSON

Repeat for at least one mutating route, such as create returning malformed
start JSON.

#### 3. Update Buddies Route

Fake command:

```python
["instance", "buddies", "--json"]
```

Fake stdout:

```json
{"buddies":[{"id":"pm","label":"PM","scope":"Own product iteration and track progression."}]}
```

Expected HTTP response remains:

```json
{"ok":true,"buddies":[{"id":"pm","label":"PM","scope":"Own product iteration and track progression."}]}
```

#### 4. Update Instances Route

Fake command:

```python
["instance", "list", "--json"]
```

Expected HTTP response remains:

```json
{"ok":true,"instances":[]}
```

#### 5. Update Create Route

Expected fake runner calls:

```python
[
    ["instance", "buddies", "--json"],
    ["instance", "start", "--buddy", "pm", "--json"],
    ["instance", "status", "inst-pm-demo", "--json"],
]
```

The Web response shape remains unchanged:

```json
{
  "ok": true,
  "instance_id": "inst-pm-demo",
  "instance": {
    "instance_id": "inst-pm-demo"
  }
}
```

#### 6. Update Input Route

Expected fake runner calls:

```python
[
    ["instance", "input", "inst-pm-demo", "--text", "Advance the brief", "--json"],
    ["instance", "status", "inst-pm-demo", "--json"],
]
```

Fake input stdout:

```json
{"instance_id":"inst-pm-demo","thread_id":"thread-demo","action":"start","turn_id":"turn-demo"}
```

Expected response includes `action` and `turn_id` from launcher JSON.

#### 7. Update Interrupt Route

Expected fake runner calls:

```python
[
    ["instance", "interrupt", "inst-pm-demo", "--json"],
    ["instance", "status", "inst-pm-demo", "--json"],
]
```

Expected response includes `turn_id` from launcher JSON.

#### 8. Update Stop Route

Expected fake runner calls:

```python
[
    ["instance", "stop", "inst-pm-demo", "--json"],
    ["instance", "status", "inst-pm-demo", "--json"],
]
```

Expected response still returns refreshed `instance`.

#### 9. Update Delete Route

Expected fake runner call:

```python
["instance", "delete", "inst-pm-demo", "--yes", "--json"]
```

Expected response remains:

```json
{"ok":true,"instance_id":"inst-pm-demo"}
```

### UI Tests

Run existing UI state tests unchanged:

```bash
node tests/web_management_ui_state.test.js
```

No browser-facing HTTP shape changes are expected, so UI state should not need
product behavior changes.

## Focused Verification Commands

Run after each relevant block:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'buddies or list or start_with_buddy or input_ or interrupt_ or stop_ or instance_delete' -q
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
```

Run the existing service-mode regression gate:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Final verification:

```bash
python3 -m pytest -q
```

## Review Checks

Before declaring done, run:

```bash
rg -n 'parse_buddies_tsv|parse_instance_list_tsv|parse_started_instance_id|parse_turn_action_output|parse_interrupt_turn_id' tools/launcher/web_management.py tests/test_web_management.py
rg -n 'buddyswitch/objects|buddyswitch/local/buddybox' tools/launcher/web_management.py tools/launcher/instance.sh tests/test_web_management.py tests/test_buddyswitch_launcher.py
rg -n 'shell=True|FastAPI|Flask|aiohttp|queue|workflow|plugin|auth' tools/launcher/web_management.py tools/launcher/instance.sh
git diff --stat
git diff
git status --short --branch
```

Expected:

- first command returns no matches
- forbidden runtime paths appear only in documentation or existing comments, not
  as write targets in changed code
- no new web framework, queue, workflow, plugin, or auth system appears
- diff is focused on launcher JSON contract, Web consumption, and tests
