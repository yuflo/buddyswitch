# Instance Start Bootstrap Cleanup Execution Prompt

Worktree: `fea-daemon`

Execute the full task described by:

- `docs/memo/2026-05-31-instance-start-bootstrap-cleanup-task.md`
- `docs/spec/2026-05-31-instance-start-bootstrap-cleanup-test-plan.md`
- `docs/spec/2026-05-31-instance-start-bootstrap-cleanup-development-plan.md`

Use SHARP: solve the current lifecycle bottleneck through the shortest validated path. Do not expand the task into a lifecycle platform.

## Required Scope

Implement exactly the current task:

1. `thread/bootstrap` gets a dedicated timeout path and one retry only for timeout-like failure.
2. Failed start after retry exhaustion cleans runtime state and writes a small `last_failure`.
3. `instance delete` blocks only on target-owned browser resources, not a foreign browser endpoint on a stale recorded port.

## Hard Non-Goals

Do not add:

- Web UI browser lifecycle special cases;
- global npm cache work;
- global Chrome DevTools MCP process sharing;
- automatic instance recreation;
- automatic deletion of failed instance directories;
- browser ownership registry;
- daemon coordination path;
- broad lifecycle state machine;
- direct edits to runtime object stores.

## TDD Loop

1. Add the focused tests from the test plan.
2. Run each focused test and confirm it fails for the missing production behavior.
3. Implement the smallest direct code change.
4. Re-run the focused test until it passes.
5. Move to the next requirement.

Use fake Codex/browser helpers. Do not launch real Chrome, real Codex, real MCP servers, or npm installs for these regressions.

## Verification

Focused:

```bash
python3 -m unittest tests.test_app_server_client.AppServerClientTests.test_thread_bootstrap_rollout_uses_dedicated_timeout -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_timeout_retries_once_and_succeeds -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_retry_failure_cleans_state_and_records_failure -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_blocks_live_target_browser_endpoint -v
```

Relevant group:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -k 'bootstrap or delete or browser or reset' -q
```

Final:

```bash
python3 -m pytest -q
git diff --check
```

Before declaring completion, inspect the diff and confirm every acceptance checklist item in the development plan is satisfied.

