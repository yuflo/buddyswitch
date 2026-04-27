# BuddySwitch CLI Command Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mixed top-level BuddySwitch launcher commands with the final `instance / data / env` command surface.

**Architecture:** Keep the launcher monolith. Refactor public dispatch and helper parsers directly; do not add compatibility aliases. Preserve private `__locked-*` entrypoints as implementation details behind the runtime lock.

**Tech Stack:** Bash launcher helpers, Python cleanup backend, existing `unittest`/`pytest` tests, README/framework docs.

---

## Final Public Command Surface

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy> [-- codex args...]
./buddyswitch-codex instance list [--buddy <buddy>]
./buddyswitch-codex instance open <id> [-- codex args...]
./buddyswitch-codex instance delete <id> [--yes]

./buddyswitch-codex data cleanup --buddy <buddy> [--yes] [--json]
./buddyswitch-codex data cleanup --app-runtime [--yes] [--json]
./buddyswitch-codex data cleanup --all-data [--yes] [--json]

./buddyswitch-codex env status [--json]
./buddyswitch-codex env browser status [--instance <id>] [--port <port>] [--profile-dir <dir>]
./buddyswitch-codex env browser ensure --instance <id> [--port <port>] [--profile-dir <dir>]
./buddyswitch-codex env reset [--yes]
```

## Non-Goals

- No `instance resume`.
- No `instance prune`.
- No `data cleanup --instance`.
- No public `workspace` command.
- No top-level public `start`, `buddy`, `cleanup`, `reset`, or `browser` aliases.
- No unknown-command fallback into Codex.
- No retention policy, daemon, supervisor, archive, or migration framework.

## Replacement Matrix

| Current public command | Final behavior |
|---|---|
| `start --buddy <buddy>` | Fail closed with hint: `instance start --buddy <buddy>` |
| bare `buddyswitch-codex [codex args...]` | Fail closed; use `codex` directly for source development |
| `buddy list` | Fail closed with hint: `instance buddies` |
| `cleanup ...` | Fail closed with hint: `data cleanup ...` |
| `reset --yes` | Fail closed with hint: `env reset --yes` |
| `browser status/ensure` | Fail closed with hint: `env browser status/ensure ...` |
| `workspace sync` | Fail closed; no public replacement |
| unknown top-level command, including `debug` | Fail closed and do not launch Codex |
| private `__locked-*` entries | Keep private and runtime-lock guarded |

## Semantics To Lock

- `instance buddies` reads `buddyswitch/manifest.toml`; it does not create or mutate runtime state.
- `instance start --buddy <buddy>` always creates a fresh instance and starts Codex in that instance workspace.
- `instance start/open` accept an optional `--` separator before Codex args; the separator is stripped before invoking Codex.
- `instance open <id>` reuses the existing instance workspace/profile; it does not restore the previous Codex transcript.
- `instance delete <id>` defaults to preview and mutates nothing. `--yes` deletes only that instance root and registered worktree.
- `data cleanup` defaults to preview and mutates nothing. `--yes` executes deletion. `--execute` and `--force` are removed.
- `data cleanup --buddy <buddy>` clears shared BuddySwitch data for that buddy and matching buddy raw scratch across all matching instances. It does not delete any instance root.
- `data cleanup --app-runtime` clears `projects/app/.runtime` under instance workspaces. It does not delete shared BuddySwitch objects or instance roots.
- `data cleanup --all-data` equals all-buddy shared data, all-buddy raw scratch, and app runtime cleanup. It does not delete instance roots, shared root, auth, Codex homes, or browser profiles.
- `env browser status/ensure --instance <id>` binds the instance first, then resolves browser port/profile/log defaults from that instance. Explicit `--port` and `--profile-dir` override the instance defaults.
- `env reset` defaults to preview and mutates nothing. `--yes` is the only public path that may delete the full `${BUDDYSWITCH_SHARED_ROOT}`.
- Active launcher/browser blockers fail closed for destructive execution.

## File Responsibilities

| File | Responsibility |
|---|---|
| `buddyswitch-codex` | Public dispatch, top-level help, `instance start`, `data`, `env`, fail-closed old command hints |
| `tools/launcher/instance.sh` | `instance buddies/list/open/delete` usage and delete preview support |
| `tools/launcher/cleanup.sh` | `data cleanup` shell safety gates, shared-state targeting, instance-local scratch cleanup |
| `scripts/env_cleanup.py` | Cleanup backend parser/plan/result names for `--buddy`, `--app-runtime`, `--all-data`, `--yes` |
| `tools/launcher/browser_cockpit.sh` | `--instance` parsing and instance-bound browser status/ensure behavior |
| `tools/launcher/env.sh` | Existing instance binding/reset root helpers reused by `env` commands |
| `README.md` | Final command surface and user-facing lifecycle/data/env explanation |
| `framework/console/app.js` | Copyable cleanup commands updated to `data cleanup ...` |
| `framework/docs/interface-spec.md` | Context panel command contract updated to final commands |
| `scripts/cleanup_buddyswitch.sh` | Delete the legacy shim; do not forward |
| `tests/test_buddyswitch_launcher.py` | Launcher command surface, instance/env behavior, old command fail-closed tests |
| `tests/test_cleanup_system.py` | `data cleanup` scope and safety tests |
| `tests/test_repo_consistency.py` | Docs and command-surface consistency checks |

## Task Plan

### Task 1: Public Command Surface Gate

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] Add failing tests that `help` lists only `instance`, `data`, `env`, and `help`.
- [ ] Add failing tests that old public commands `start`, `buddy`, `cleanup`, `reset`, `browser`, and `workspace` return exit code `2` with the correct new-command hint.
- [ ] Add a failing test that unknown top-level command `debug` returns exit code `2` and does not invoke fake Codex.
- [ ] Update `print_help` to show the final command surface only.
- [ ] Replace the top-level `main` public dispatch with only `instance`, `data`, `env`, `help`, and private `__locked-*`.
- [ ] Keep private locked entries callable only through existing runtime-lock checks.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  tests/test_repo_consistency.py -q
```

Expected: the updated command-surface tests pass.

### Task 2: Instance Namespace

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add failing tests for `instance buddies`, proving it lists manifest buddies and does not create `${BUDDYSWITCH_SHARED_ROOT}`.
- [ ] Add failing tests for `instance start --buddy pm -- debug prompt-input ...`, proving `--` is stripped and Codex receives only the trailing args.
- [ ] Add failing tests that `instance open <id> -- debug prompt-input ...` strips `--` and reuses the existing instance.
- [ ] Add failing tests for `instance delete <id>` preview: exit code `0`, prints target instance root, prints that shared state is kept, and does not delete anything.
- [ ] Keep `instance delete <id> --yes` as the only execution path for deleting an instance root.
- [ ] Move manifest listing from old `buddy list` into `instance buddies`.
- [ ] Route `instance start` through the existing start/bootstrap path, requiring `--buddy <buddy>`.
- [ ] Update empty instance-list hint to `./buddyswitch-codex instance start --buddy <buddy>`.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_reuses_existing_instance_environment \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_removes_only_target_instance_without_shared_state \
  -q
```

Expected: instance start/open/delete tests pass under the new command names.

### Task 3: Data Cleanup Namespace

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `scripts/env_cleanup.py`
- Delete: `scripts/cleanup_buddyswitch.sh`
- Modify: `tests/test_cleanup_system.py`

- [ ] Add failing tests for `data cleanup --buddy market` preview and `--yes` execution.
- [ ] Add failing tests for `data cleanup --app-runtime` preview and `--yes` execution across instance workspaces.
- [ ] Add failing tests for `data cleanup --all-data --yes` proving it keeps `${shared_root}/instances/*` and `${shared_root}`.
- [ ] Add failing tests that `--execute`, `--force`, `--agent`, `--all-agents`, `--project`, and `--all-storage` are rejected through public `data cleanup`.
- [ ] Add failing tests that active launcher/browser blockers still block `data cleanup ... --yes`.
- [ ] Replace cleanup public parser with `--buddy`, `--app-runtime`, `--all-data`, `--yes`, and `--json`.
- [ ] Remove source-checkout cleanup and legacy workspace fallback from public cleanup execution.
- [ ] Remove the shell branch that deletes instance roots during data cleanup.
- [ ] Implement `--all-data` as all-buddy shared data cleanup, all-buddy raw scratch cleanup, and app runtime cleanup; do not call old `--all-storage`.
- [ ] Delete `scripts/cleanup_buddyswitch.sh` and update tests/docs that referenced it.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected: cleanup tests pass and no data cleanup path deletes instance roots.

### Task 4: Env Namespace

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add failing tests for `env reset` preview: exit code `0`, prints shared root impact, and does not delete shared root.
- [ ] Keep `env reset --yes` as the only public full shared-root deletion path.
- [ ] Add failing tests for `env browser status --instance <id>` using the instance browser port/profile from `instance.json` and instance root.
- [ ] Add failing tests for `env browser ensure --instance <id>` binding instance env before browser defaults and updating the instance browser port when needed.
- [ ] Add failing tests for `env status` and `env status --json`, covering shared root, instance count, active blockers, browser state, data/app-runtime size categories, and next command hints.
- [ ] Add `env_main` dispatch for `status`, `browser status`, `browser ensure`, and `reset`.
- [ ] In browser parser, support `--instance <id>` before resolving browser defaults. If `--instance` and explicit `--port`/`--profile-dir` are both provided, explicit values override the instance defaults.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_registered_instance_worktrees \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_blocks_live_instance_browser_without_pid_marker \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_browser_ensure_is_blocked_when_runtime_lock_is_held \
  -q
```

Expected: env reset/browser tests pass under the new namespace.

### Task 5: Docs, Console, And Consistency

**Files:**
- Modify: `README.md`
- Modify: `framework/console/app.js`
- Modify: `framework/docs/interface-spec.md`
- Modify: `docs/whiteboard/2026-04-23-multi-instance-buddy-runtime-architecture.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] Replace every active user-facing command example with the final command surface.
- [ ] Remove public documentation for `start`, `buddy`, `cleanup`, `reset`, `browser`, and `workspace`.
- [ ] Update Context Panel copyable commands to:

```bash
./buddyswitch-codex data cleanup --buddy <buddy>
./buddyswitch-codex data cleanup --app-runtime
./buddyswitch-codex data cleanup --all-data
```

- [ ] Update docs to state that cleanup commands are preview by default and execute only with `--yes`.
- [ ] Add repo consistency checks that active docs include `instance start`, `instance buddies`, `data cleanup`, `env browser`, and `env reset`.
- [ ] Add repo consistency checks that active docs do not include old public command examples.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: docs consistency tests pass.

## Final Verification

Run the full relevant suite outside the sandbox if needed, because launcher tests create git worktrees and bind local sockets.

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_cleanup_system.py \
  tests/test_switch_runtime.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

```text
git diff --check exits 0
pytest exits 0
```

## Stop Conditions

- Stop if any old public command still launches Codex.
- Stop if any `data cleanup` path deletes an instance root or shared root.
- Stop if docs or console still show old public commands.
- Stop if `env reset --yes` is not the only public command that can remove `${BUDDYSWITCH_SHARED_ROOT}`.
- Stop if implementation requires adding `resume`, `prune`, per-instance cleanup, or public compatibility aliases.
