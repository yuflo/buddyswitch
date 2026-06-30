# fea-webui and fea-daemon Current Main Merge Plan

> **For agentic workers:** Implement this plan task-by-task. Keep the merge direct: preserve the latest branch behavior, remove replaced legacy paths, and do not add compatibility tracks.

**Goal:** Merge the current `fea-webui` and `fea-daemon` heads into `main` with Web IM history cache correctness and Task Sys side-frame lifecycle fixes verified together.

**Architecture:** `fea-webui` changes only the browser management UI state cache and its Node contract tests. `fea-daemon` changes Task Sys domain/runtime behavior, task tool feedback, side-thread lease tracking, daemon/web status projection, and Python tests. The integrated tree should keep one Web IM state path and one Task Sys side-frame lifecycle path.

**Tech Stack:** Python launcher/runtime code, env tool modules, browser management JavaScript, Node UI contract tests, `pytest`, `unittest`, `py_compile`, `bash -n`, `git merge-tree`.

---

## Current Baseline

- `git fetch --all --prune` completed with no remote changes.
- `main` is clean at `1929e32b0c1fdc6ac6e38ba700bfd6f93ba177e6` and matches `origin/main`.
- `fea-webui` is clean at `f82500dd7c8d074d8204c5c0c2d4184eeb48cf04` and matches `origin/fea-webui`.
- `fea-daemon` is clean at `5807b8093d9bc1860ea7698ec73ca093d384d3da` and matches `origin/fea-daemon`.
- `git merge-base main fea-webui`, `git merge-base main fea-daemon`, and `git merge-base fea-webui fea-daemon` all resolve to current `main` (`1929e32`).

## Conflict, Dependency, And Association Assessment

### Branch Shape

- `fea-webui` has one commit over `main`: `f82500d fix webui im history cache`.
- `fea-daemon` has one commit over `main`: `5807b80 Fix task sys side frame lifecycle`.
- Both branches start from the same current `main`, so there is no older shared feature stack to reconcile in this pass.

### Conflict Assessment

- `git merge-tree --write-tree main fea-webui` produced tree `23c5dcfd97408408492d7e76daf2ffc61611b9b4` with no conflict records.
- `git merge-tree --write-tree main fea-daemon` produced tree `c968edce2beba4d79fc70a62e6bc30dc75e5b676` with no conflict records.
- Synthetic sequential dry-runs in both orders produced the same final tree `30561c44e08b61900c0a6899bc098c62574e0093`.
- `comm -12` over the two branch file lists returned no paths, so there is no direct file overlap.
- Result: no textual conflicts are expected, and merge order should not affect final content.

### Dependency Assessment

- Neither branch changes package, lockfile, Python dependency, Node dependency, Rust, Go, or other dependency manifest files.
- `git diff --check main...fea-webui` and `git diff --check main...fea-daemon` both passed with no output.
- Result: no dependency installation, lockfile reconciliation, or whitespace cleanup is expected before focused verification.

### Association Assessment

- `fea-webui` changes:
  - `tools/launcher/assets/web-management/app.js`
  - `tests/web_management_ui_contract.test.js`
  - `tests/web_management_ui_state.test.js`
  - `docs/spec/2026-06-30-webui-im-history-state-forward-fix-plan.md`
- `fea-webui` behavior to preserve:
  - IM conversation cache is bound to the selected actor identity.
  - Switching actors, deleting actors, creating actors, and refreshing actor console clear stale IM rows.
  - Missing direct conversation history is treated as empty history instead of a user-facing error.
  - Connection-wide IM events are acknowledged even when off-selected actor messages are not rendered.
- `fea-daemon` changes:
  - `scripts/env/domain/task_sys.py`
  - `scripts/env/tool_runtime/context.py`
  - `scripts/env/tools/task_sys/_impl.py`
  - `scripts/env/tools/task_sys/tool.py`
  - `tools/launcher/task_sys_runtime.py`
  - `tools/launcher/side_thread_registry.py`
  - `tools/launcher/daemon_core.py`
  - `tools/launcher/web_management.py`
  - focused Python tests and Task Sys lifecycle docs under `docs/spec/task-sys-side-frame-lifecycle/`
- `fea-daemon` behavior to preserve:
  - Task Sys can record recoverable side runtime failures without counting them as active tasks.
  - Task Sys side-frame dispatch creates a task-bound side lease, retries failed dispatch, and records structured failure metadata.
  - `task_sys.close` and `task_sys.need_parent` clean up task-bound side leases and return cleanup feedback.
  - Web actor console exposes recoverable Task Sys status separately from active Task Sys status.
- Cross-branch association:
  - The only indirect join is Web Management: `fea-webui` updates browser-side actor/IM state, while `fea-daemon` updates server-side actor console Task Sys projection.
  - The final tree must keep both without adding browser-side daemon compatibility branches or daemon-side iMessage delivery inference.

## Merge Plan

### Task 1: Record Current Plan

- [x] Replace the stale merge-plan baseline with the current branch hashes and evidence.
- [x] Commit this plan while `main` is otherwise clean.

Verification:

```bash
git status --short --branch
git diff --check
```

Expected: only this plan file is modified before the planning commit, and `git diff --check` has no output.

### Task 2: Merge `fea-webui`

- [ ] Run `git merge --no-ff --no-commit fea-webui`.
- [ ] Keep the actor-identity-bound Web IM cache behavior.
- [ ] Remove or resolve any unexpected residue by direct replacement, not aliases or dual read/write paths.
- [ ] Run focused Web UI verification.
- [ ] Commit the merge.

Focused verification:

```bash
node --check tools/launcher/assets/web-management/app.js
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --check
```

Expected: JavaScript syntax passes, Node UI contract/state tests pass, and whitespace check has no output.

### Task 3: Merge `fea-daemon`

- [ ] Run `git merge --no-ff --no-commit fea-daemon`.
- [ ] Keep explicit recoverable side runtime failure states and side lease cleanup feedback.
- [ ] Keep daemon/status observability read-only; do not infer external iMessage delivery from daemon health.
- [ ] Run focused daemon/status/runtime verification.
- [ ] Commit the merge.

Focused verification:

```bash
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/tool_runtime/context.py scripts/env/tools/task_sys/_impl.py scripts/env/tools/task_sys/tool.py tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py tools/launcher/daemon_core.py tools/launcher/web_management.py
bash -n buddyswitch-codex
bash -n tools/launcher/runtime_broker.sh
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_buddyswitch_launcher.py tests/test_daemon_service_contract.py tests/test_web_management.py
git diff --check
```

Expected: compile and shell syntax pass, focused Python tests pass, and whitespace check has no output.

### Task 4: Final Integration Verification

- [ ] Prove both feature branches are ancestors of `main`.
- [ ] Run combined focused verification that covers both branches and the Web Management association point.
- [ ] Run residue scans for retired taskbox/task tool paths, browser-side IM compatibility residue, and daemon-side sensitive logging/platform residue.
- [ ] Inspect final git status and recent history.

Final verification:

```bash
git merge-base --is-ancestor fea-webui main
git merge-base --is-ancestor fea-daemon main
node --check tools/launcher/assets/web-management/app.js
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/tool_runtime/context.py scripts/env/tools/task_sys/_impl.py scripts/env/tools/task_sys/tool.py tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py tools/launcher/daemon_core.py tools/launcher/web_management.py
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_buddyswitch_launcher.py tests/test_daemon_service_contract.py tests/test_web_management.py
git diff --check
git status --short --branch
```

Residue scans:

```bash
rg -n "task\\.current|task\\.capture|task\\.checkout|task__current|task__checkout|TaskViewModel|E_ACTIVE_TASK_REQUIRED|task\\.active_anchor|taskbox|task_management" scripts tools buddyswitch docs/arch -S
rg -n "buildWebImConversationUrl|ensureWebImSession|applyImEventsPayload|messageTouchesKnownOrSelectedActor|imEventCursor|event_cursor|participant_token|connection_key" tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js -S
rg -n "raw_message|message_content|artifact_body|full_prompt|credentials|tool_payload|event bus|trace id|sampling" tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py -S
git diff --name-only 1929e32b0c1fdc6ac6e38ba700bfd6f93ba177e6..HEAD
```

Expected:

- Both target branches are ancestors of `main`.
- Focused Node, Python compile, shell syntax, and Python tests pass.
- `git diff --check` has no output.
- Old taskbox/task tool live paths are absent.
- Browser IM residue scan has no output outside negative contract assertions if the tests intentionally mention forbidden symbols by concatenated strings.
- Status/logging implementation scan does not expose raw message, prompt, credential, or tool payload content.
- Final changed files are attributable to the two target branch commits plus this merge plan.

## Acceptance Criteria

- `main` contains `f82500d` and `5807b80`.
- The stale previous merge-plan completion record is replaced by current evidence.
- Web IM history cache behavior is actor-identity-bound and does not render off-selected actor messages.
- Recoverable Task Sys side-frame failure and cleanup behavior is preserved.
- Web actor console exposes active and recoverable Task Sys state without mixing the two.
- No old taskbox/task tool compatibility path, browser-side Web IM compatibility path, generic event bus, tracing platform, feature flag, or dual compatibility mode is introduced.
- Focused verification passes, or any blocker is recorded with the exact failing command and root cause before further changes.

## Execution Log

This section is updated after each merge or verification block with exact command evidence.
