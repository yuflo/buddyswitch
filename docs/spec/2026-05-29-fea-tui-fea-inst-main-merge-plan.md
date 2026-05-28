# fea-tui + fea-inst Main Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `fea-tui` and `fea-inst` into `main`, verify the combined product state with a consistent Python 3.13 environment, and push `main` to `origin/main`.

**Architecture:** This is an integration-only change. Preserve both feature branches as authored, add this merge plan as the required execution artifact, merge into `main` with explicit merge commits, and rely on Git conflict checks plus pytest behavior verification rather than compatibility wrappers or code changes.

**Tech Stack:** Git worktrees, Bash launcher scripts, Python 3.13.5 from `/Users/chen/miniconda3/bin/python3`, pytest 9.0.3, BuddySwitch launcher/runtime tests.

---

## Current State Snapshot

- Repository root: `/Users/chen/Dev/buddyswitch`
- Planning worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tui`
- Integration target worktree: `/Users/chen/Dev/buddyswitch`
- `main`: `5d071be8e50aeac64847bf0edd762aaa3ee15593`
- `fea-tui`: `56e7a6b7d96ba4e362c0bc3b5144c411f2627e2a`
- `fea-inst`: `f06ff69fdc67b196292aac86493fc1461ad278f0`
- Merge base for `main`, `fea-tui`, and `fea-inst`: `5d071be8e50aeac64847bf0edd762aaa3ee15593`

## Critical Testing Rule

Every Python verification command in this plan must start with:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1
```

Do not run tests with bare `python3`; on this machine bare `python3` can resolve to Apple Python 3.9 through `/usr/bin/python3`, and launcher subprocesses also use `python3` from `PATH`.

Before any pytest command, verify the interpreter:

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
git fetch origin --prune
```

Expected: exit code 0.

- [ ] **Step 2: Confirm all involved worktrees are clean**

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui status --short --branch
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-inst status --short --branch
```

Expected:

```text
## main...origin/main
## fea-tui...origin/fea-tui
## fea-inst...origin/fea-inst
```

- [ ] **Step 3: Confirm local branches match fetched remote refs**

```bash
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui rev-list --left-right --count origin/main...main
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui rev-list --left-right --count origin/fea-tui...fea-tui
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui rev-list --left-right --count origin/fea-inst...fea-inst
```

Expected:

```text
0	0
0	0
0	0
```

## Task 2: Commit This Plan on fea-tui

**Files:**
- Create: `docs/spec/2026-05-29-fea-tui-fea-inst-main-merge-plan.md`

- [ ] **Step 1: Review plan file is present**

```bash
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui status --short
```

Expected: one added plan file.

- [ ] **Step 2: Commit the plan artifact**

```bash
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui add docs/spec/2026-05-29-fea-tui-fea-inst-main-merge-plan.md
git -C /Users/chen/Dev/buddyswitch/.worktrees/fea-tui commit -m "docs: plan fea tui and inst merge"
```

Expected: a new `fea-tui` commit containing only this plan file.

## Task 3: Merge Branches into main

**Files:**
- Modify through Git merge: `main` branch in `/Users/chen/Dev/buddyswitch`

- [ ] **Step 1: Predict merge conflicts without modifying the worktree**

```bash
git -C /Users/chen/Dev/buddyswitch merge-tree --write-tree main fea-tui
git -C /Users/chen/Dev/buddyswitch merge-tree --write-tree main fea-inst
git -C /Users/chen/Dev/buddyswitch merge-tree --write-tree fea-tui fea-inst
```

Expected: each command exits 0 and prints a tree hash, with no conflict diagnostics.

- [ ] **Step 2: Merge fea-tui into main**

```bash
git -C /Users/chen/Dev/buddyswitch merge --no-ff --no-edit fea-tui
```

Expected: exit code 0, no conflict markers, merge commit created on `main`.

- [ ] **Step 3: Merge fea-inst into main**

```bash
git -C /Users/chen/Dev/buddyswitch merge --no-ff --no-edit fea-inst
```

Expected: exit code 0, no conflict markers, merge commit created on `main`.

- [ ] **Step 4: Confirm merged status is clean and ahead of origin**

```bash
git -C /Users/chen/Dev/buddyswitch status --short --branch
git -C /Users/chen/Dev/buddyswitch log --oneline --decorate -5
```

Expected: `main` is clean and ahead of `origin/main`; recent log includes merge commits for `fea-tui` and `fea-inst`.

## Task 4: Verify the Combined State

**Files:**
- Test: `tests/`

- [ ] **Step 1: Re-confirm Python environment**

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

- [ ] **Step 2: Run focused integration gate for both branches**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_input_wrapper.py \
  tests/test_app_server_client.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_task_checkout_handler.py \
  tests/test_daemon_core.py \
  tests/test_daemon_core_decoupling.py \
  tests/test_submit_turn.py \
  tests/test_web_management.py \
  tests/test_daemon_service_contract.py \
  tests/test_runtime_actor_profile.py \
  tests/test_role_action_auth.py \
  tests/test_env_tool_router.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_message_env_tool.py \
  tests/test_env_tool_identity.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_clean_runtime_environment.py \
  -q
```

Expected: exit code 0.

- [ ] **Step 3: Run the full repository test suite**

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected: exit code 0. This is the completion gate for "全部测试通过".

- [ ] **Step 4: Confirm no generated files changed the worktree**

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
- exact Python interpreter used
- focused gate result
- full suite result
- pushed `origin/main` commit
- any remaining risk
