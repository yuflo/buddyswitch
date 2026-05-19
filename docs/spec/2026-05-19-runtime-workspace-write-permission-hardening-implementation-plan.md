# Runtime Workspace Write Permission Hardening Implementation Plan

Date: 2026-05-19
Status: ready for implementation

## Goal

Prevent BuddySwitch product runtime sessions from writing launcher-owned runtime workspace paths
such as `workspace/scripts/**`, even when the model tries to create helper scripts.

This is a focused permission/config fix. Do not add workflow routers, long AGENTS instructions,
message polling abstractions, or new coordination systems.

## Scope

Modify only the launcher-generated Codex permission profile and its tests.

Expected files:

- Modify: `tools/launcher/codex_config.py`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify if needed: `tests/test_env_layer_boundaries.py`

## Steps

1. Add a failing permission test.

   Add focused coverage proving the dev runtime permission profile does not grant write access to
   runtime workspace source/tool surfaces, especially:

   - `<workspace_dir>/scripts/**`
   - `<workspace_dir>/tools/**`
   - `<workspace_dir>/tests/**`
   - `<workspace_dir>/docs/**`
   - `<workspace_dir>/buddyswitch/objects/**`
   - `<workspace_dir>/buddyswitch/local/buddybox/<non-active-buddy>/**`

   The test must still prove the allowed write paths remain available:

   - shared project workspace when `project.access=write`
   - active buddybox directory
   - instance home / codex-home / xdg config
   - safe temp roots

2. Implement the minimal permission-profile change.

   Update `tools/launcher/codex_config.py` so the generated `buddyswitch-runtime` profile keeps the
   runtime workspace root read-only and marks launcher/runtime contract surfaces as non-writable.

   The fix should be config-level enforcement, not prompt text. Avoid adding AGENTS wording except
   if an existing short boundary sentence becomes inaccurate.

3. Run focused verification.

   Required commands:

   ```bash
   python3 -m pytest tests/test_buddy_env_sandbox.py -q
   python3 -m pytest tests/test_env_layer_boundaries.py -q
   ```

   Also inspect a generated runtime config or focused test fixture to confirm:

   - `project_workspace_dir` is writable for dev;
   - active buddybox is writable;
   - runtime `workspace_dir` is not writable;
   - runtime `scripts/**` is not writable;
   - the source repo checkout remains blocked.

4. Run broader config/launcher checks and residue scan.

   Required commands:

   ```bash
   python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_runtime_agents.py -q
   rg -n "workspace/scripts|subagent_.*poll|sandbox_approval.*true|Would you like to make the following edits" tools scripts tests docs -g '!docs/spec/2026-05-19-runtime-workspace-write-permission-hardening-implementation-plan.md'
   ```

   If the existing Codex permission model cannot express a non-escalatable write deny for these
   paths, stop and record the blocker clearly. Do not claim completion until either the hard block is
   verified or the limitation is documented with an equivalent tested mitigation.
