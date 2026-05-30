# fea-daemon + fea-skill Main Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `fea-daemon` and `fea-skill` into `main`, preserve the daemon actor-address communication upgrade and browser non-activating helper upgrade together, verify the combined state, and push `main` to `origin/main`.

**Architecture:** This is an integration change with one known test-file conflict. Merge `fea-daemon` first because it changes lower-level runtime actor/message/daemon contracts, then merge `fea-skill` and resolve the shared launcher test by keeping daemon's flexible port probe plus skill's cockpit proxy registration assertion. Do not add compatibility wrappers; fix only real integration breakage surfaced by tests.

**Tech Stack:** Git worktrees, Bash launcher scripts, Python 3.13.5 from `/Users/chen/miniconda3/bin/python3`, pytest 9.0.3, BuddySwitch runtime env tools, launcher daemon/browser tests.

---

## Current State Snapshot

- Repository root and target worktree: `/Users/chen/Dev/buddyswitch`
- Source worktree `fea-daemon`: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`
- Source worktree `fea-skill`: `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill`
- `main`: `1cf79b59baa73af694a17f76f3b13d7ff4e62e66`
- `origin/main`: `1cf79b59baa73af694a17f76f3b13d7ff4e62e66`
- `fea-daemon`: `ab1ef196d2570d4640e84e188e83e36251a76049`
- `origin/fea-daemon`: `41907e454daf6b0391b9253ed5f1ab14621b5134`
- `fea-skill`: `ea7b6389046812f9948a0ff6277c1212e162e922`
- `origin/fea-skill`: `ea7b6389046812f9948a0ff6277c1212e162e922`
- Merge base for `main`, `fea-daemon`, and `fea-skill`: `1cf79b59baa73af694a17f76f3b13d7ff4e62e66`
- Note: the user request says `fae-skill`; the actual branch/worktree present in this checkout is `fea-skill`.

## Known Integration Findings

- Single-branch merges into `main` are clean.
- Combined merge has one textual conflict in `tests/test_buddyswitch_launcher.py`.
- Correct conflict resolution:

```python
expected_browser_port = self._first_available_local_port(9223)
self._assert_cockpit_proxy_registration(
    cockpit_add["argv"],
    f"http://127.0.0.1:{expected_browser_port}",
)
```

- Keep `fea-daemon` message/daemon actor-address API changes:
  - `create_message(from_actor_address=..., to_actor_address=...)`
  - `prepare_send_request(source_actor_address=...)`
  - `filter_inbox_messages(active_actor_address=...)`
  - `ToolContext.actor_address`
  - `ToolContext.daemon`
  - `run_daemon(..., mailbox_handlers=...)`
- Keep `fea-skill` browser changes:
  - `scripts/env/cdp_background_page.py`
  - `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - cockpit MCP registration through the BuddySwitch proxy, not direct `chrome-devtools-mcp@latest`.

## Critical Testing Rule

Every Python verification command must start with:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1
```

Before pytest verification, confirm the interpreter:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH python3 --version
PATH=/Users/chen/miniconda3/bin:$PATH which python3
PATH=/Users/chen/miniconda3/bin:$PATH python3 -m pytest --version
```

Expected output:

```text
Python 3.13.5
/Users/chen/miniconda3/bin/python3
pytest 9.0.3
```

## Task 1: Refresh and Confirm Inputs

**Files:**
- Read-only: Git refs and worktree status

- [ ] **Step 1: Fetch latest refs**

```bash
git -C /Users/chen/Dev/buddyswitch fetch origin --prune
```

Expected: exit code 0.

- [ ] **Step 2: Confirm involved worktrees**

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon status --short --branch
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-skill status --short --branch
```

Expected:

```text
## main...origin/main
## fea-daemon...origin/fea-daemon [ahead 1]
?? docs/memo/2026-05-30-message-product-experience-no-residual-repair-task.md
## fea-skill...origin/fea-skill
```

The untracked `fea-daemon` memo is not part of the branch merge unless explicitly added later.

- [ ] **Step 3: Confirm local/remote divergence**

```bash
git -C /Users/chen/Dev/buddyswitch rev-list --left-right --count origin/main...main
git -C /Users/chen/Dev/buddyswitch rev-list --left-right --count origin/fea-daemon...fea-daemon
git -C /Users/chen/Dev/buddyswitch rev-list --left-right --count origin/fea-skill...fea-skill
```

Expected:

```text
0	0
0	1
0	0
```

## Task 2: Commit This Plan on main

**Files:**
- Create: `docs/spec/2026-05-30-fea-daemon-fea-skill-main-merge-implementation-plan.md`

- [ ] **Step 1: Review plan file is the only main worktree change**

```bash
git -C /Users/chen/Dev/buddyswitch status --short
```

Expected: one added plan file.

- [ ] **Step 2: Commit the plan artifact**

```bash
git -C /Users/chen/Dev/buddyswitch add docs/spec/2026-05-30-fea-daemon-fea-skill-main-merge-implementation-plan.md
git -C /Users/chen/Dev/buddyswitch commit -m "docs: plan daemon and skill merge"
```

Expected: a new `main` commit containing only this plan file.

## Task 3: Merge Branches into main

**Files:**
- Merge through Git: `main` branch in `/Users/chen/Dev/buddyswitch`
- Resolve: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Merge `fea-daemon` first**

```bash
git -C /Users/chen/Dev/buddyswitch merge --no-ff --no-edit fea-daemon
```

Expected: exit code 0, merge commit created.

- [ ] **Step 2: Merge `fea-skill` second**

```bash
git -C /Users/chen/Dev/buddyswitch merge --no-ff --no-edit fea-skill
```

Expected: conflict in `tests/test_buddyswitch_launcher.py`.

- [ ] **Step 3: Resolve launcher test conflict**

In `tests/test_buddyswitch_launcher.py`, keep:

```python
expected_browser_port = self._first_available_local_port(9223)
```

and:

```python
self._assert_cockpit_proxy_registration(cockpit_add["argv"], f"http://127.0.0.1:{expected_browser_port}")
```

Then remove conflict markers and continue the merge:

```bash
git -C /Users/chen/Dev/buddyswitch add tests/test_buddyswitch_launcher.py
git -C /Users/chen/Dev/buddyswitch commit --no-edit
```

Expected: `main` has explicit merge commits for `fea-daemon` and `fea-skill`.

- [ ] **Step 4: Confirm no conflict markers or stale direct cockpit registration**

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
rg -n "^(<<<<<<<|=======|>>>>>>>)" /Users/chen/Dev/buddyswitch
rg -n "chrome-devtools-mcp@latest" /Users/chen/Dev/buddyswitch/tools/launcher /Users/chen/Dev/buddyswitch/tests
```

Expected: clean `main` worktree ahead of origin, no conflict markers, no launcher/test expectation that newly registers direct `chrome-devtools-mcp@latest`.

## Task 4: Verify the Combined State

**Files:**
- Test: `tests/`
- Compile: `scripts/env/`, `tools/launcher/`

- [ ] **Step 1: Confirm Python environment**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH python3 --version
PATH=/Users/chen/miniconda3/bin:$PATH which python3
PATH=/Users/chen/miniconda3/bin:$PATH python3 -m pytest --version
```

Expected:

```text
Python 3.13.5
/Users/chen/miniconda3/bin/python3
pytest 9.0.3
```

- [ ] **Step 2: Run focused browser/search integration gate**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_search_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_allocates_next_browser_port_when_default_is_busy \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_required_buddy_ready_page_launches_codex \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url \
  -q
```

Expected: exit code 0.

- [ ] **Step 3: Run focused daemon/message integration gate**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_message_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_actor_profile.py \
  tests/test_daemon_core.py \
  tests/test_instance_daemon_entrypoint.py \
  tests/test_daemon_service_contract.py \
  tests/test_daemon_mailbox.py \
  tests/test_message_available_handler.py \
  tests/test_daemon_communication_boundary.py \
  tests/test_central_daemon_service.py \
  -q
```

Expected: exit code 0.

- [ ] **Step 4: Compile changed runtime code**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q scripts/env tools/launcher
```

Expected: exit code 0.

- [ ] **Step 5: Run the full repository test suite**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected: exit code 0. This is the final automated test gate before push.

- [ ] **Step 6: Confirm no generated files changed the worktree**

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

Expected: clean `main` worktree, ahead of `origin/main` until push.

## Task 5: Push and Confirm Remote Sync

**Files:**
- Remote ref: `origin/main`

- [ ] **Step 1: Push main to origin**

```bash
git -C /Users/chen/Dev/buddyswitch push origin main
```

Expected: exit code 0.

- [ ] **Step 2: Fetch and confirm sync**

```bash
git -C /Users/chen/Dev/buddyswitch fetch origin --prune
git -C /Users/chen/Dev/buddyswitch status --short --branch
git -C /Users/chen/Dev/buddyswitch rev-list --left-right --count origin/main...main
```

Expected:

```text
## main...origin/main
0	0
```

- [ ] **Step 3: Report final evidence**

Report:

- plan file path
- merge order
- conflict resolution
- exact Python interpreter used
- focused browser/search gate result
- focused daemon/message gate result
- compile result
- full suite result
- pushed `origin/main` commit
- remaining risk
