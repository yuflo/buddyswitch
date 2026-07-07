# Daemon Side Triage Residue Removal Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unused daemon side-triage reuse surface completely so actor runtime side-thread creation has one current path: Task Sys `start_side` creates a fresh task-bound side-thread, and host-control `/side` starts or explicitly sends to a side-thread by id.

**Architecture:** Delete the non task-bound reuse API instead of preserving compatibility. `DaemonRuntime` should expose parent prompt operations plus Task Sys execute/cleanup only. `side_thread_lifecycle` should own concrete start/send/cleanup operations, not "find or reuse" policy.

**Tech Stack:** Python launcher modules under `tools/launcher`, env/runtime tests under `tests`, `unittest`, scoped `rg` residue scans.

---

## Scope

Remove this retired live surface:

- `DaemonRuntime.submit_side_triage_prompt(...)`
- `side_thread_lifecycle.find_or_start_side_thread(...)`
- `side_thread_registry.find_open_side_thread(...)`
- `side_thread_registry.py find-open`
- tests that define the above as supported behavior
- fake runtime methods in IM/Track handler tests that still name side-triage prompt submission

Keep these current surfaces:

- `side_thread_lifecycle.start_side_thread(...)`
- `side_thread_lifecycle.send_to_side_thread(...)`
- `side_thread_lifecycle.cleanup_side_thread(...)`
- `side_thread_lifecycle.cleanup_task_side_lease(...)`
- host-control `./buddyswitch-codex instance side ...`
- Task Sys `execute_task_sys_instruction(...)` and `cleanup_task_sys_side_lease(...)`

Historical docs under `docs/memo` are evidence, not cleanup targets. The new residue gate must exclude historical docs.

## Principles Applied

Read before planning:

- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `AGENTS.md`

Operational conclusions:

- Do not keep a guard or compatibility branch for retired side-triage reuse semantics.
- Do not keep tests that teach `submit_side_triage_prompt` as a public runtime method.
- Prove behavior with focused tests and prove cleanup with a scoped live-surface residue scan.
- Exclude historical docs from residue enforcement.
- Do not expand this into a broader side-thread lifecycle redesign.

## Current Evidence

Production references after excluding `docs/**` and `tests/**`:

```text
tools/launcher/daemon_core.py: DaemonRuntime.submit_side_triage_prompt(...)
tools/launcher/daemon_core.py: side_thread_lifecycle.find_or_start_side_thread(... purpose="daemon.side_triage")
tools/launcher/side_thread_lifecycle.py: find_or_start_side_thread(...)
tools/launcher/side_thread_registry.py: find_open_side_thread(...)
tools/launcher/side_thread_registry.py: find-open CLI subcommand
```

Test references that currently preserve the old surface:

```text
tests/test_daemon_service_contract.py:
  test_submit_side_triage_prompt_starts_or_reuses_side_and_records_runtime_facts
  test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods

tests/test_side_thread_lifecycle.py:
  test_find_or_start_rejects_model_or_effort_when_existing_side_thread_would_be_reused
  _seed_side_thread default purpose="daemon.side_triage"

tests/test_side_thread_registry.py:
  test_find_open_side_thread_returns_first_open_row_for_parent
  test_find_open_side_thread_skips_task_bound_task_sys_leases

tests/test_im_wake_handler.py:
  fake runtime method submit_side_triage_prompt

tests/test_track_comment_added_handler.py:
  fake runtime method submit_side_triage_prompt
```

## New Contract

Task Sys actor-side processing:

```text
user input / IM wake / Track comment
  -> task_sys.ingest(...)
  -> start_side instruction
  -> task_sys_runtime.execute_instruction(...)
  -> side_thread_lifecycle.start_side_thread(...)
  -> fresh task-bound side-thread
```

Host-control side conversation:

```text
instance side <actor-id> --text ...
  -> side_thread_lifecycle.start_side_thread(... purpose="host_control.side")

instance side <actor-id> --side-thread-id <id> --text ...
  -> side_thread_lifecycle.send_to_side_thread(...)
```

No current live path should search for a reusable unnamed side-thread.

---

### Task 1: Add A Failing Residue Gate

**Files:**
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add the scoped residue test**

Add this method to `RepoConsistencyTests` near the existing side-thread lifecycle consistency tests:

```python
    def test_daemon_side_reuse_surface_is_removed(self) -> None:
        targets = ["tools/launcher", "scripts/env", "buddyswitch-codex", "tests"]
        forbidden = (
            "submit_" + "side_triage_prompt",
            "daemon." + "side_triage",
            "find_or_" + "start_side_thread",
            "find_" + "open_side_thread",
            "find-" + "open",
            "start_" + "or_reuse_side_triage",
            "start_" + "side_triage",
            "send_" + "side_triage",
            "close_" + "side_triage",
        )
        hits: list[str] = []
        for token in forbidden:
            hits.extend(self._scan_targets(token, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))
```

Do not include `docs` in `targets`.

- [ ] **Step 2: Run the new residue test and confirm it fails**

Run:

```bash
python -m unittest -q tests.test_repo_consistency.RepoConsistencyTests.test_daemon_side_reuse_surface_is_removed
```

Expected before cleanup: FAIL with hits in `tools/launcher/daemon_core.py`, `tools/launcher/side_thread_lifecycle.py`, `tools/launcher/side_thread_registry.py`, and old tests.

---

### Task 2: Delete The Daemon Runtime Method

**Files:**
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_daemon_service_contract.py`

- [ ] **Step 1: Remove the method from production**

Delete `DaemonRuntime.submit_side_triage_prompt(...)` entirely from `tools/launcher/daemon_core.py`.

After deletion, `DaemonRuntime` should expose these public methods:

```python
{
    "parent_activity",
    "submit_parent_prompt",
    "execute_task_sys_instruction",
    "cleanup_task_sys_side_lease",
}
```

- [ ] **Step 2: Remove the old behavior test**

Delete this test from `tests/test_daemon_service_contract.py`:

```python
test_submit_side_triage_prompt_starts_or_reuses_side_and_records_runtime_facts
```

Do not replace it with a negative compatibility test. The residue gate owns the proof that the old surface is absent.

- [ ] **Step 3: Update the public surface test**

Change `test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods` expected set to:

```python
{
    "parent_activity",
    "submit_parent_prompt",
    "execute_task_sys_instruction",
    "cleanup_task_sys_side_lease",
}
```

- [ ] **Step 4: Update the old-name exclusion test**

Add the retired current name to `test_daemon_runtime_handler_facing_surface_excludes_old_action_names` without writing the full token contiguously if it would be scanned by the residue test:

```python
"submit_" + "side_triage_prompt",
```

- [ ] **Step 5: Run focused daemon contract tests**

Run:

```bash
python -m unittest -q tests.test_daemon_service_contract
```

Expected after Task 2 plus later cleanup tasks: PASS. If run immediately after only Task 2, it may still fail the new residue gate through lifecycle/registry/test references; continue with the plan.

---

### Task 3: Delete The Lifecycle Reuse Helper

**Files:**
- Modify: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tests/test_side_thread_lifecycle.py`

- [ ] **Step 1: Remove `find_or_start_side_thread`**

Delete the entire `find_or_start_side_thread(...)` function from `tools/launcher/side_thread_lifecycle.py`.

Keep:

```python
start_side_thread(...)
send_to_side_thread(...)
cleanup_side_thread(...)
cleanup_task_side_lease(...)
```

- [ ] **Step 2: Remove the reuse-specific lifecycle test**

Delete:

```python
test_find_or_start_rejects_model_or_effort_when_existing_side_thread_would_be_reused
```

- [ ] **Step 3: Rename the test helper default purpose**

Change `_seed_side_thread(...)` default purpose from:

```python
purpose: str = "daemon.side_triage",
```

to:

```python
purpose: str = "host_control.side",
```

This preserves explicit send/cleanup tests without teaching daemon side-triage semantics.

- [ ] **Step 4: Run focused lifecycle tests**

Run:

```bash
python -m unittest -q tests.test_side_thread_lifecycle
```

Expected after Task 3 plus registry cleanup: PASS.

---

### Task 4: Delete Registry Find-Open Support

**Files:**
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tests/test_side_thread_registry.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Remove registry helper and private predicate**

Delete these from `tools/launcher/side_thread_registry.py`:

```python
def _is_task_bound_lease(row: dict[str, Any]) -> bool:
    ...

def find_open_side_thread(...):
    ...
```

- [ ] **Step 2: Remove CLI `find-open` subcommand**

Delete this parser branch:

```python
find = subparsers.add_parser("find-open")
_add_common(find, side=False)
find.set_defaults(func=_command_find_open)
```

Delete `_command_find_open(...)`.

Keep `find_task_side_thread(...)`; Task Sys cleanup still needs it.

- [ ] **Step 3: Remove registry tests for find-open**

Delete these tests:

```python
test_find_open_side_thread_returns_first_open_row_for_parent
test_find_open_side_thread_skips_task_bound_task_sys_leases
```

- [ ] **Step 4: Update side-thread lifecycle boundary consistency**

In `tests/test_repo_consistency.py::test_side_thread_lifecycle_boundary_has_no_direct_call_residue`, remove `find_open_side_thread` from the forbidden direct-call pattern because the function no longer exists.

The registry part should become:

```python
+ r"|side_thread_registry\."
+ r"(register_side_thread|require_side_thread|find_task_side_thread|unregister_side_thread)"
```

- [ ] **Step 5: Run focused registry tests**

Run:

```bash
python -m unittest -q tests.test_side_thread_registry
```

Expected: PASS.

---

### Task 5: Remove Test Fake Runtime Residue

**Files:**
- Modify: `tests/test_im_wake_handler.py`
- Modify: `tests/test_track_comment_added_handler.py`

- [ ] **Step 1: Remove IM fake side-prompt method**

Delete this fake method from `_Runtime` in `tests/test_im_wake_handler.py`:

```python
def submit_side_triage_prompt(self, prompt: str, **kwargs: Any) -> None:
    self.calls.append({"method": "submit_side_triage_prompt", "prompt": prompt, **kwargs})
    raise AssertionError("IM wake handler must not submit side prompts")
```

The existing assertion that the only runtime call is `execute_task_sys_instruction` is sufficient.

- [ ] **Step 2: Remove Track fake side-prompt method**

Delete this fake method from `FakeDaemonRuntime` in `tests/test_track_comment_added_handler.py`:

```python
def submit_side_triage_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
    self.calls.append(
        {
            "method": "submit_side_triage_prompt",
            "text": text,
            "handler_name": handler_name,
            "origin_id": origin_id,
        }
    )
    raise AssertionError("Track comment handler must not submit side prompts")
```

- [ ] **Step 3: Run handler tests**

Run:

```bash
python -m unittest -q tests.test_im_wake_handler tests.test_track_comment_added_handler
```

Expected: PASS.

---

### Task 6: Verify Current Main Paths Still Work

**Files:**
- No edits.

- [ ] **Step 1: Run Task Sys side creation tests**

Run:

```bash
python -m unittest -q tests.test_task_sys_runtime_executor
```

Expected: PASS. This proves Task Sys still creates fresh task-bound side-threads through `start_side_thread(...)`.

- [ ] **Step 2: Run launcher host-control side tests**

Run:

```bash
python -m unittest -q \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_creates_child_injects_boundary_and_sends_text \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_start_accepts_model_and_effort_as_thread_fork_only_overrides \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_send_existing_active_child_steers_side_not_parent \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_send_existing_idle_child_starts_side_turn \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_close_interrupts_registered_child_and_removes_registry
```

Expected: PASS. This proves manual side create/send/close still works without reusable side-thread discovery.

- [ ] **Step 3: Run Web management side API tests**

Run:

```bash
python -m unittest -q \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_create_route_delegates_and_reports_side_thread_id \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_route_passes_model_and_effort_only_for_new_side_thread \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_send_route_delegates_existing_side \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_close_route_delegates_and_reports_side_thread_id \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_route_rejects_model_or_effort_with_existing_side_thread_id
```

Expected: PASS.

---

### Task 7: Run Residue And Broader Relevant Verification

**Files:**
- No edits unless verification finds a live residue.

- [ ] **Step 1: Run exact live-surface residue scan**

Run:

```bash
rg -n 'submit_side_triage_prompt|daemon\.side_triage|find_or_start_side_thread|find_open_side_thread|find-open|start_or_reuse_side_triage|start_side_triage|send_side_triage|close_side_triage' \
  tools/launcher scripts/env buddyswitch-codex tests
```

Expected: no output, exit code 1.

- [ ] **Step 2: Run residue tests**

Run:

```bash
python -m unittest -q \
  tests.test_repo_consistency.RepoConsistencyTests.test_daemon_side_reuse_surface_is_removed \
  tests.test_repo_consistency.RepoConsistencyTests.test_side_thread_lifecycle_boundary_has_no_direct_call_residue
```

Expected: PASS.

- [ ] **Step 3: Run focused side-thread suites**

Run:

```bash
python -m unittest -q \
  tests.test_side_thread_lifecycle \
  tests.test_side_thread_registry \
  tests.test_task_sys_runtime_executor \
  tests.test_daemon_service_contract \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler
```

Expected: PASS.

- [ ] **Step 4: Run relevant launcher/API side suites**

Run:

```bash
python -m unittest -q \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_input_json_creates_task_sys_task_when_thread_idle \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_input_json_creates_task_sys_task_when_thread_active \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_start_accepts_model_and_effort_as_thread_fork_only_overrides \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_send_existing_active_child_steers_side_not_parent \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_side_close_interrupts_registered_child_and_removes_registry \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_route_passes_model_and_effort_only_for_new_side_thread \
  tests.test_web_management.WebManagementHTTPActionTests.test_side_send_route_delegates_existing_side
```

Expected: PASS.

## Acceptance Checklist

- [ ] `DaemonRuntime` no longer has `submit_side_triage_prompt`.
- [ ] `side_thread_lifecycle` no longer has `find_or_start_side_thread`.
- [ ] `side_thread_registry` no longer has `find_open_side_thread` or `find-open`.
- [ ] IM and Track handlers only depend on `execute_task_sys_instruction` for side processing.
- [ ] Task Sys still creates fresh task-bound side-threads.
- [ ] Host-control side create/send/close still works by explicit start/send/cleanup operations.
- [ ] Scoped live-surface residue scan has no hits outside historical docs.

## Explicit Non-Goals

- Do not delete or rewrite historical `docs/memo` evidence.
- Do not remove host-control `instance side`.
- Do not remove explicit `send_to_side_thread(...)`.
- Do not change side-thread model/effort support for `start_side_thread(...)`.
- Do not add compatibility aliases or deprecation wrappers.

## Plan Self-Review

- Spec coverage: covers production code, tests, registry CLI support, fakes, residue gates, and verification.
- Placeholder scan: no placeholders, no deferred cleanup.
- Boundary check: removes old reuse policy instead of guarding it; keeps current Task Sys and host-control paths intact.
