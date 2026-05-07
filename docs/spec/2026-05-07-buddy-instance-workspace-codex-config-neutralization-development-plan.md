# Buddy Instance Workspace Codex Config Neutralization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure product-mode buddy instances are not governed by the repo-tracked workspace `.codex/config.toml`, so launcher-managed instance `CODEX_HOME/config.toml` is the effective Codex permission source.

**Architecture:** Keep the existing launcher-owned `codex-home/config.toml` patcher as the single product-mode permission source. After any product instance execution worktree is created or refreshed, launcher removes only the workspace project-level `.codex/config.toml` inside the instance worktree before Codex starts. Development checkouts and non-instance launcher paths keep their repo `.codex/config.toml`.

**Tech Stack:** Bash launcher scripts, Python `unittest`, fake launcher binaries used by existing integration tests, Codex TOML config files.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout. Keep this change scoped to the `dev0210` worktree.

## Current Bottleneck

PM buddy product testing showed Codex asking for approval before running `python3 scripts/turn_runtime.py prepare`. The launcher-generated instance config already grants the runtime broker socket and disables request-permission prompts, but the instance workspace is a git worktree and checks out repo-tracked `.codex/config.toml`, which contains `approval_policy = "on-request"` and can override the user-level instance config.

The bottleneck is duplicated effective Codex configuration in product mode. The fix is to make launcher responsible for neutralizing the workspace project config in product instances.

## Confirmed Facts

- Repo-tracked project config exists at `.codex/config.toml` and contains `approval_policy = "on-request"` plus `sandbox_mode = "workspace-write"`.
- Product instance workspaces are git worktrees under `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- `tools/launcher/codex_config.py` patches `${BUDDYSWITCH_CODEX_HOME}/config.toml` with `default_permissions = "buddyswitch-runtime"`, granular approval policy, MCP approve mode, and broker socket allowlist.
- `tools/launcher/env.sh` currently patches only `${BUDDYSWITCH_CODEX_HOME}/config.toml`.
- `buddyswitch-codex` calls `buddyswitch_workspace_prepare_execution_worktree` during `instance start`, and calls the equivalent sync/install path during `instance open`.
- Official Codex config rules already verified in the prior investigation: project `.codex/config.toml` participates in config loading and has higher precedence than user config for overlapping keys.

## Scope

In scope:

- Remove or neutralize only `"$BUDDYSWITCH_WORKSPACE_DIR/.codex/config.toml"` for launcher-managed product instances.
- Make the behavior idempotent for both new `instance start` and existing `instance open`.
- Preserve source checkout `.codex/config.toml` for BuddySwitch development mode.
- Add tests proving the user-visible permission source cannot be shadowed by workspace project config.

Out of scope:

- Rewriting the repo-root `.codex/config.toml`.
- Adding a second full managed config copy under workspace `.codex`.
- Changing `tools/launcher/codex_config.py` permission semantics.
- Changing runtime broker, env profile, browser cockpit, or buddy skill behavior.

## File Map

Modify:

- `tools/launcher/workspace.sh`: add product-instance project config neutralization and call it after workspace checkout/sync.
- `buddyswitch-codex`: call the neutralization during `instance open` if the implementation keeps open bootstrap as an explicit sequence instead of routing through a shared workspace helper.
- `tests/test_buddyswitch_launcher.py`: extend functional launcher tests for `instance start` and `instance open`.

Do not modify:

- `.codex/config.toml`
- `tools/launcher/codex_config.py`
- `buddyswitch/manifest.toml`

## Implementation Tasks

### Task 1: Add Failing Product-Mode Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Extend the existing `instance start` lifecycle test**

In `test_start_with_buddy_wires_instance_env_and_lifecycle`, after `workspace_dir = instance_root / "workspace"`, assert that the product workspace project config has been neutralized while the launcher-managed user config remains present.

Add this assertion block near the existing `codex-home/config.toml` checks:

```python
            workspace_project_config = workspace_dir / ".codex" / "config.toml"
            self.assertFalse(
                workspace_project_config.exists(),
                "product instance workspace must not keep project .codex/config.toml because it can override launcher-managed CODEX_HOME config",
            )
            self.assertTrue((instance_root / "codex-home" / "config.toml").exists())
```

- [ ] **Step 2: Extend the existing `instance open` config test**

In `test_instance_open_patches_existing_config_and_preserves_mcp_sections`, seed a stale workspace project config before invoking `instance open`:

```python
            workspace_project_config = workspace_dir / ".codex" / "config.toml"
            workspace_project_config.parent.mkdir(parents=True, exist_ok=True)
            workspace_project_config.write_text(
                'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n',
                encoding="utf-8",
            )
```

After `open_result` succeeds and the `codex-home/config.toml` assertions pass, add:

```python
            self.assertFalse(
                workspace_project_config.exists(),
                "instance open must remove stale workspace project config before launching Codex",
            )
```

- [ ] **Step 3: Run the targeted tests and verify they fail for the expected reason**

Run:

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_start_with_buddy_wires_instance_env_and_lifecycle tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_instance_open_patches_existing_config_and_preserves_mcp_sections -q
```

Expected result before implementation:

```text
FAILED ... product instance workspace must not keep project .codex/config.toml
```

The failure must be caused by the workspace project config still existing. If the tests fail because fake browser, fake codex, or instance setup is broken, fix that test setup issue before implementing launcher behavior.

### Task 2: Add Launcher Neutralization

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Possibly modify: `buddyswitch-codex`

- [ ] **Step 1: Add a focused workspace helper**

Add this function after `buddyswitch_workspace_is_instance_mode` in `tools/launcher/workspace.sh`:

```bash
buddyswitch_workspace_neutralize_project_codex_config() {
  local workspace_dir project_config project_config_dir

  if ! buddyswitch_workspace_is_instance_mode; then
    return 0
  fi

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  project_config="${workspace_dir}/.codex/config.toml"
  project_config_dir="$(dirname "${project_config}")"

  buddyswitch_workspace_require_path_under_shared_root \
    "workspace project Codex config" \
    "${project_config}" >/dev/null || return $?

  if [[ -e "${project_config}" || -L "${project_config}" ]]; then
    rm -f "${project_config}"
  fi

  rmdir "${project_config_dir}" >/dev/null 2>&1 || true
}
```

Behavior requirements:

- No-op unless `BUDDYSWITCH_INSTANCE_ID` is set.
- Remove only the project-level config file inside the launcher-managed instance workspace.
- Treat symlinks as removable.
- Do not remove repo-root `.codex/config.toml`.
- Do not write a replacement config into workspace `.codex`.

- [ ] **Step 2: Call the helper after workspace checkout/sync**

Update `buddyswitch_workspace_sync_runtime_surface` so neutralization runs after runtime surface sync:

```bash
  python3 - "${repo_root}" "${workspace_dir}" <<'PY'
  ...
PY

  buddyswitch_workspace_neutralize_project_codex_config
```

This covers:

- fresh `instance start`, because `buddyswitch_workspace_ensure_execution_worktree` calls `buddyswitch_workspace_sync_runtime_surface`;
- rebuilt execution worktrees;
- any explicit runtime surface sync that happens before product launch.

- [ ] **Step 3: Cover `instance open` if the direct open path does not already hit the helper**

Inspect `instance_open_locked_bootstrap`. If its existing `buddyswitch_workspace_sync_runtime_surface` call now invokes the helper, no additional change is needed.

If future code movement bypasses that function, add this explicit call immediately after workspace sync and before `buddyswitch_ensure_shared_env`:

```bash
  buddyswitch_workspace_neutralize_project_codex_config
```

Do not add a second config patcher in `env.sh`.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_start_with_buddy_wires_instance_env_and_lifecycle tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_instance_open_patches_existing_config_and_preserves_mcp_sections -q
```

Expected result:

```text
2 passed
```

### Task 3: Add a Non-Instance Regression Check

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add a test that development checkout config is not removed**

Add a test that invokes a non-instance launcher command with fake `codex` and asserts the repo checkout `.codex/config.toml` still exists afterward.

Use product behavior wording for the test name:

```python
    def test_non_instance_launch_keeps_repo_project_codex_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            repo_project_config = ROOT / ".codex" / "config.toml"
            before = repo_project_config.read_text(encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            completed = subprocess.run(
                [str(LAUNCHER), "debug", "prompt-input", "development mode"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(repo_project_config.exists())
            self.assertEqual(repo_project_config.read_text(encoding="utf-8"), before)
```

If `debug prompt-input` is not accepted for non-instance launch in the current fake Codex setup, replace the command with the smallest existing non-instance launcher invocation that reaches `buddyswitch_run_codex`.

- [ ] **Step 2: Run the non-instance regression**

Run:

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_non_instance_launch_keeps_repo_project_codex_config -q
```

Expected result:

```text
1 passed
```

### Task 4: Full Verification And Review

**Files:**

- No additional source changes unless tests reveal a real regression.

- [ ] **Step 1: Run launcher config and sandbox tests**

Run:

```bash
pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py -q
```

Expected result:

```text
passed
```

- [ ] **Step 2: Run focused source search**

Run:

```bash
rg -n 'approval_policy = "on-request"|sandbox_mode = "workspace-write"' .codex tools/launcher tests docs/spec
```

Expected result:

- `.codex/config.toml` may still contain the development checkout defaults.
- Tests may contain negative fixtures that seed stale workspace config.
- Product launcher assets should not contain a workspace config copy path that recreates `.codex/config.toml`.

- [ ] **Step 3: Optional manual product smoke if local Codex is available**

Run:

```bash
./buddyswitch-codex instance start --buddy pm -- --version
```

Then inspect the created instance:

```bash
find "$HOME/.codex-buddyswitch/instances" -maxdepth 4 -path '*/workspace/.codex/config.toml' -print
```

Expected result:

```text
```

No `workspace/.codex/config.toml` should print for the new product instance.

## Acceptance Criteria

- Product `instance start --buddy pm` leaves no `workspace/.codex/config.toml` in the new instance workspace.
- Product `instance open <instance-id>` removes stale `workspace/.codex/config.toml` before Codex launch.
- `${instance_root}/codex-home/config.toml` still contains `default_permissions = "buddyswitch-runtime"`, granular approval policy, MCP approve mode, and broker socket allowlist.
- Development checkout `.codex/config.toml` remains tracked and untouched.
- No implementation writes a second full managed config into workspace `.codex`.
- Targeted launcher tests and sandbox/config tests pass.

## Stop Condition

Stop only after tests prove that product-mode buddy instances cannot be pulled back to `approval_policy = "on-request"` by a workspace project config, and that development mode still keeps its repo project config intact.
