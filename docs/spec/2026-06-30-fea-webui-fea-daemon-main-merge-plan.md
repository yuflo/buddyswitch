# fea-webui and fea-daemon Main Merge Plan

> **For agentic workers:** Implement this plan task-by-task. Keep the merge direct: preserve latest branch behavior, remove replaced legacy paths, and do not add compatibility tracks.

**Goal:** Merge current `fea-webui` and `fea-daemon` into `main` with the shared Task Sys rebuild, the iMessage/Web IM API boundary optimization, and daemon/runtime observability all verified together.

**Architecture:** `fea-webui` and `fea-daemon` share the Task Sys replacement base, then diverge into independent product heads. The integrated tree should keep one Task Sys path, one External IM/iMessage projection path, and one daemon status/log projection path.

**Tech Stack:** Python launcher/runtime code, env tool modules, shell launcher scripts, Node UI contract tests, `pytest`, `unittest`, `py_compile`, `git merge-tree`.

---

## Current Baseline

- `main` is clean at `25b44e7f33a65d2cab9b9ed8578391ef386593e4` and matches `origin/main`.
- `fea-webui` is clean at `3d55b816901b0b4b51241fc754012582ec0ae198` and matches `origin/fea-webui`.
- `fea-daemon` is clean at `b46ce12943e8eef7023375d8b1f3fee779499461` and matches `origin/fea-daemon`.
- `git fetch --all --prune` completed with no remote changes.
- `main` already contains the earlier `fea-webui + fea-tool` merge through `25b44e7`; this plan covers the newer `fea-webui + fea-daemon` heads only.

## Conflict, Dependency, And Association Assessment

### Branch Shape

- `git merge-base main fea-webui` and `git merge-base main fea-daemon` both resolve to `25b44e7`.
- `fea-webui` and `fea-daemon` share branch base `96621e573c2d89453b3e9698199adc3d82131ef1`.
- Shared commits on both branches:
  - `ced94b8 Rebuild task sys proactive model`
  - `96621e5 Fix task sys memo optimizations`
- Divergent branch heads:
  - `3d55b81 Optimize iMessage IM API boundary`
  - `b46ce12 Complete task sys IM observability`

### Conflict Assessment

- `git merge-tree --write-tree main fea-webui` produced tree `fd39c7f514d07bae9296a97ec691f48509fcc59b` with no conflict records.
- `git merge-tree --write-tree main fea-daemon` produced tree `563bfedf9741fa3587a9a2eaf90b4e4681810cc8` with no conflict records.
- Synthetic sequential dry-runs in both orders produced the same final tree `41b3cadee05e7a0a5c4d7da9baf1b3bd99a348af`.
- Result: no textual conflicts are expected, and merge order should not affect final content.

### Dependency Assessment

- Neither branch changes package, lockfile, Python dependency, Node dependency, Rust, Go, or other dependency manifest files.
- `git diff --check main...fea-webui` and `git diff --check main...fea-daemon` both passed.
- Result: no dependency installation, lockfile reconciliation, or whitespace cleanup is expected before testing.

### Association Assessment

- The large overlap between both branches and `main` is the shared Task Sys rebuild. Keep this as the new single path and do not preserve deleted taskbox/task tool modules.
- `fea-webui` unique files cover External IM ack semantics, Web-scoped IM projection, split iMessage worker loops, and current iMessage smoke documentation:
  - `scripts/env/services/messages.py`
  - `tools/launcher/external_im_session.py`
  - `tools/launcher/im_http_router.py`
  - `tools/launcher/imessage_channel.py`
  - `tools/launcher/web_management.py`
  - focused iMessage/Web tests and docs under `docs/spec/imessage-channel-im-api-boundary-optimization/`
- `fea-daemon` unique files cover explicit Task Sys close/status semantics and compact service log metadata:
  - `scripts/runtime_kernel/lifecycle.py`
  - `tools/launcher/app_server.py`
  - `tools/launcher/daemon_core.py`
  - `tools/launcher/runtime_broker.sh`
  - `tools/launcher/runtime_event_log.py`
  - focused daemon/status/runtime tests and docs under `docs/spec/task-sys-im-completion-status-observability/`
- The divergent `fea-webui` and `fea-daemon` commits do not modify the same files after their shared base.
- `fea-daemon` explicitly avoided iMessage channel/API files while it was developed; the final merge may contain both branches, but no daemon-specific compatibility path should be added to those files.

## Merge Plan

### Task 1: Record This Plan

- [x] Write the current merge assessment and test plan under `docs/spec`.
- [x] Commit the plan while `main` is otherwise clean.

Verification:

```bash
git status --short --branch
```

Expected: only this plan file is new before the planning commit.

### Task 2: Merge `fea-webui`

- [x] Run `git merge --no-ff --no-commit fea-webui`.
- [x] Keep the shared Task Sys replacement and the `fea-webui` iMessage/Web IM API boundary changes.
- [x] Remove or resolve any unexpected residue by direct replacement, not aliases or dual read/write paths.
- [x] Run focused Task Sys and iMessage/Web verification.
- [x] Commit the merge.

Focused verification:

```bash
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/services/messages.py tools/launcher/task_sys_ingress.py tools/launcher/task_sys_runtime.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/imessage_channel.py tools/launcher/web_management.py
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_task_sys_checkpoint.py tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py tests/test_imessage_channel.py
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --check
```

Expected: compile passes, focused Python and Node tests pass, whitespace check has no output.

### Task 3: Merge `fea-daemon`

- [x] Run `git merge --no-ff --no-commit fea-daemon`.
- [x] Keep explicit Task Sys close semantics, parent-frame completion requirements, daemon status Task Sys projection, runtime breadcrumbs, and compact log metadata.
- [x] Keep daemon/status observability read-only; do not infer external iMessage delivery from daemon health.
- [x] Run focused daemon/status/runtime verification.
- [x] Commit the merge.

Focused verification:

```bash
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py tools/launcher/task_sys_runtime.py
bash -n buddyswitch-codex
bash -n tools/launcher/runtime_broker.sh
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py tests/test_buddyswitch_launcher.py tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py
git diff --check
```

Expected: compile and shell syntax pass, focused daemon/runtime tests pass, whitespace check has no output.

### Task 4: Final Integration Verification

- [x] Prove both feature branches are ancestors of `main`.
- [x] Run broad Python verification from `main`.
- [x] Run Node UI contract verification.
- [x] Run residue scans for retired taskbox/task tool paths, retired iMessage worker-ordering residue, sensitive log metadata exposure, and accidental daemon-to-iMessage branch leakage.
- [x] Inspect final git status and recent history.

Broad verification:

```bash
git merge-base --is-ancestor fea-webui main
git merge-base --is-ancestor fea-daemon main
python3 -m pytest -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --check
git status --short --branch
```

Residue scans:

```bash
rg -n "task\\.current|task\\.capture|task\\.checkout|task__current|task__checkout|TaskViewModel|E_ACTIVE_TASK_REQUIRED|task\\.active_anchor|taskbox|task_management" scripts tools buddyswitch docs/arch -S
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests::test_live_surfaces_do_not_teach_serial_reply_wait_semantics
rg -n "raw_message|message_content|artifact_body|full_prompt|credentials|tool_payload|event bus|trace id|sampling" tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py tests docs/spec -S
git diff --name-only 25b44e7..HEAD | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected:

- Both target branches are ancestors of `main`.
- Broad Python and Node tests pass.
- `git diff --check` has no output.
- Old taskbox/task tool live paths are absent.
- Retired iMessage worker-ordering residue is absent outside the current iMessage optimization records.
- Status/logging code does not expose raw message, prompt, credential, or tool payload content.
- Any final diff hits for iMessage/Web files are attributable to the intentional `fea-webui` merge, not daemon-specific edits.

## Acceptance Criteria

- `main` contains the latest `fea-webui` and `fea-daemon` commits.
- The shared Task Sys rebuild is preserved as the only actor-driving task path.
- No old taskbox/task tool compatibility path remains live.
- External IM event ack, Web-scoped projection, and split iMessage worker behavior are preserved.
- Explicit `task_sys.close`, parent-frame completion requirements, daemon Task Sys status projection, runtime breadcrumb logs, and compact status log metadata are preserved.
- No generic event bus, tracing platform, feature flag, or dual compatibility mode is introduced.
- Focused and broad verification pass, or any blocker is recorded with exact failing command and root cause before further changes.

## Final Merge Verification 2026-06-30

Merge commits:

```text
b0817bb docs: plan fea webui daemon merge
3b2b687 Merge branch 'fea-webui'
367e456 Merge branch 'fea-daemon'
83fd567 test: classify merge implementation specs
```

Branch ancestry:

```text
git merge-base --is-ancestor fea-webui main
exit 0

git merge-base --is-ancestor fea-daemon main
exit 0
```

Focused `fea-webui` verification:

```text
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/services/messages.py tools/launcher/task_sys_ingress.py tools/launcher/task_sys_runtime.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/imessage_channel.py tools/launcher/web_management.py
passed

python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_task_sys_checkpoint.py tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py tests/test_imessage_channel.py
144 passed, 60 subtests passed in 113.01s

node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
2 test files passed

git diff --check
no output
```

Focused `fea-daemon` verification:

```text
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py tools/launcher/task_sys_runtime.py
passed

bash -n buddyswitch-codex
passed

bash -n tools/launcher/runtime_broker.sh
passed

python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py tests/test_buddyswitch_launcher.py tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py
303 passed, 498 subtests passed in 644.84s

git diff --check
no output
```

Final integration verification:

```text
python3 -m pytest -q
1128 passed, 1605 subtests passed in 804.08s

node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
2 test files passed

python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests::test_live_surfaces_do_not_teach_serial_reply_wait_semantics
1 passed

python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_docs_spec_drift_filter_rejects_unmarked_live_guidance tests/test_repo_consistency.py::RepoConsistencyTests::test_stable_guidance_does_not_point_to_internal_tool_contract_surfaces
2 passed

rg -n "task\\.current|task\\.capture|task\\.checkout|task__current|task__checkout|TaskViewModel|E_ACTIVE_TASK_REQUIRED|task\\.active_anchor|taskbox|task_management" scripts tools buddyswitch docs/arch -S
no output

rg -n "raw_message|message_content|artifact_body|full_prompt|credentials|tool_payload|event bus|trace id|sampling" tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py -S
no output

git diff --check
no output
```

Residue interpretation:

- The broad sensitive-term scan across tests and specs reports historical records, current non-goal text, and negative assertions. The implementation-only scan over status/logging code has no hits.
- Final iMessage/Web file hits from `git diff --name-only 25b44e7..HEAD` are exactly the intentional `fea-webui` files: `tests/test_external_im_session.py`, `tests/test_im_http_router.py`, `tests/test_imessage_channel.py`, `tests/test_web_management.py`, `tools/launcher/external_im_session.py`, `tools/launcher/im_http_router.py`, `tools/launcher/imessage_channel.py`, and `tools/launcher/web_management.py`.
- The first broad run exposed that the repo-consistency docs/spec context filter did not classify the new implementation-record directories or merge-plan docs. Commit `83fd567` fixed the filter narrowly and added assertions that unmarked stable guidance remains rejected.

Remaining risk:

- Live macOS/iMessage delivery was not manually smoke-tested in this merge pass. Automated worker and projection tests cover the merged delayed-control and ack behavior.
- Runtime service tests exercise fake launcher/service paths; external daemon behavior still depends on host process state outside the unit test environment.
