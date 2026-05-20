# Clean Runtime Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Runtime behavior changes must follow `superpowers:test-driven-development`: write and verify the failing test before editing production code.

**Goal:** Rebuild BuddySwitch product runtime sessions so Codex sees a clean, searchable workspace while runtime objects and buddybox private files remain accessible only through broker-routed env tools.

**Architecture:** Split the host-visible workspace from the broker-owned state root. Remove runtime object and buddybox storage projections from the ordinary workspace. Bind the runtime broker to `shared/state`, generate a Codex permission profile that explicitly protects source/state roots and disables sandbox escalation, and add host-visible regression tests for ordinary exploration commands.

**Tech Stack:** Bash launcher helpers, Python runtime broker, Python env repos/services, Codex permission profile TOML generation, `pytest`, `unittest`, Codex CLI sandbox smoke tests, `rg`, `git`.

---

## Confirmed Target And Key Problems

This is a complete forward repair, not a transition plan.

The task is complete only when all of these are true:

- Ordinary Codex exploration from a product runtime workspace does not hit `Operation not permitted`.
- `buddyswitch/objects/**` is no longer a visible workspace projection.
- Buddybox private files are not normal workspace files that sub-agents locate through search.
- Runtime object state and buddybox private files still work through env tools.
- Product-session Codex config no longer depends on broad root read plus visible denied child paths as the runtime boundary.
- Product-session Codex config no longer invites unsandboxed retry for expected sandbox failures.
- Dev/non-dev source access behavior stays intact.
- No prompt, AGENTS, or skill command workaround is used as the fix.

The key broken contract is:

```text
visible workspace path + denied sandbox permission + sandbox approval prompt
```

The forward contract is:

```text
visible workspace paths are safe to explore
runtime state is broker-owned
private files are tool-backed by logical_name
```

## Native Codex Constraint

A local Codex macOS sandbox smoke on this worktree showed that a profile with `"/" = "none"` plus
explicit workspace and system read grants exits `134` before running a basic shell command. A profile
with `"/" = "read"` runs the same command successfully.

Therefore this plan does not pretend pure filesystem allowlisting is currently the shortest verified
path. The forward repair is to remove denied runtime-state projections from the visible workspace,
explicitly protect source and state roots, and disable sandbox escalation prompts. If future Codex
versions support a working pure allowlist profile, that can be a later simplification, not a blocker
for fixing the current prompt loop.

## Non-Goals

- Do not add a generic sandbox framework.
- Do not add a workflow engine, command router, or sub-agent scheduler.
- Do not preserve direct workspace access to runtime objects for compatibility.
- Do not teach Codex to avoid `rg`, `find`, `git status`, or `cat`.
- Do not broaden project source write access.
- Do not make buddybox product-readable or cross-buddy-readable.

## Files To Modify

Tests:

- Create: `tests/test_clean_runtime_environment.py`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_buddybox_env_tool.py`
- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `tests/test_buddyswitch_launcher.py`

Runtime and launcher:

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env_legacy_store.py`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `tools/launcher/runtime_broker.sh`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/codex_config.py`
- Modify: `scripts/env/tools/context/service.py`
- Modify: `scripts/env/domain/buddybox_workspace.py`
- Modify: `scripts/env/tools/buddybox/service.py`

Docs:

- Keep this plan and the test plan as the authoritative implementation handoff.
- Do not add runtime behavior mirrors to AGENTS.

## Task 1: Add Failing Clean Runtime Environment Tests

**Files:**

- Create: `tests/test_clean_runtime_environment.py`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Create host-visible workspace tests**

Create `tests/test_clean_runtime_environment.py` with test cases for the functional requirements in
`docs/spec/2026-05-20-clean-runtime-environment-test-plan.md`:

- fresh runtime workspace has no `buddyswitch/objects`;
- fresh runtime workspace has no `buddyswitch/local/buddybox/<active_buddy>`;
- `rg --files`, `rg -n`, and `git status --short --untracked-files=all -- .` do not emit `Operation not permitted`;
- stale object and buddybox projections are removed without deleting `shared/state` files;
- active AGENTS and skills do not gain command-blacklist workaround text.

- [ ] **Step 2: Add permission-profile tests**

In `tests/test_buddy_env_sandbox.py`, replace old expectations that depend on visible workspace child
denies with requirements from C1:

- generated product profile does not require `workspace/buddyswitch/objects` or active buddybox child denies for correctness;
- `sandbox_approval = false`;
- source checkout is not writable;
- state root is not readable or writable;
- active buddybox path is not a direct writable filesystem root;
- project workspace remains `read` for PM and `write` for Dev;
- broker socket allowlist still works.

- [ ] **Step 3: Add broker root tests**

In `tests/test_runtime_broker.py`, update broker lifecycle/status coverage so it expects distinct
roots:

```text
runtime_workspace_root = <shared>/instances/<id>/workspace
runtime_state_root     = <shared>/state
```

Also add an env.tool call through the live broker that creates a track and asserts:

```text
<shared>/state/buddyswitch/objects/tracks/<track_id>.json exists
<workspace>/buddyswitch/objects/tracks/<track_id>.json does not exist
```

- [ ] **Step 4: Add buddybox storage tests**

In `tests/test_buddybox_env_tool.py`, add broker-routed coverage proving:

```text
buddybox.write logical_name=coordination/a-log.md succeeds
<state-root>/buddyswitch/local/buddybox/<active>/coordination/a-log.md exists
<workspace>/buddyswitch/local/buddybox/<active>/coordination/a-log.md does not exist
buddybox.read returns the file body
buddybox.list returns coordination/a-log.md
```

- [ ] **Step 5: Run the focused tests and verify they fail**

Run:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_runtime_broker.py \
  tests/test_buddybox_env_tool.py \
  -q
```

Expected before implementation: failures showing old workspace projections, broad-root-read config,
sandbox approval enabled, workspace-root state writes, or workspace-root buddybox writes.

## Task 2: Split Runtime State Root From Host Workspace Root

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env_legacy_store.py`

- [ ] **Step 1: Add explicit root concepts**

In `scripts/env/repos/runtime_files.py`, keep these distinct:

```text
ROOT / WORKSPACE_ROOT: host-visible runtime workspace
STATE_ROOT: broker-owned runtime state root
OBJECTS_ROOT: STATE_ROOT/buddyswitch/objects
LOCAL_ROOT: STATE_ROOT/buddyswitch/local
BUDDYBOX_LOCAL_DIR: STATE_ROOT/buddyswitch/local/buddybox
```

Add a public function:

```python
def refresh_runtime_roots_from_env() -> None:
    _recompute_runtime_roots()
```

This gives the broker a supported way to refresh roots after setting `BUDDYSWITCH_STATE_ROOT`.

- [ ] **Step 2: Make buddybox storage state-root-backed**

Change `buddybox_local_dir(instance_payload=None)` so it returns:

```text
STATE_ROOT/buddyswitch/local/buddybox
```

It must not derive storage from `instance_payload["workspace_dir"]`.

- [ ] **Step 3: Keep runtime workspace discovery separate**

Keep `runtime_workspace_root(instance_payload)` as the host-visible workspace root. It should still
return `instance_payload["workspace_dir"]` for context and status reporting.

- [ ] **Step 4: Update write-root validation**

Update `require_runtime_workspace_write_root` so object writes are allowed when `STATE_ROOT` is the
launcher-managed state root for an active runtime session.

Accepted write roots:

- temporary test roots created by `RuntimeWorkspaceTestMixin`;
- broker sessions with `BUDDYSWITCH_STATE_ROOT` under `<shared>/state` and `BUDDYSWITCH_INSTANCE_ID` set;
- launcher runtime workspaces that still carry the runtime AGENTS header during tests that intentionally use a single root.

Rejected write roots:

- source checkout root;
- arbitrary paths outside `BUDDYSWITCH_SHARED_ROOT`;
- host-visible runtime workspace when it is not also the explicit test runtime root.

- [ ] **Step 5: Re-export updated roots**

Update `scripts/env_store.py` and `scripts/env_legacy_store.py` so their exported `STATE_ROOT`,
`OBJECTS_ROOT`, `BUDDYBOX_LOCAL_DIR`, and helper functions follow the refreshed values from
`runtime_files`.

- [ ] **Step 6: Run root-focused tests**

Run:

```bash
python3 -m pytest tests/test_env_store_v2.py tests/test_buddybox_env_tool.py -q
```

Expected after this task: root helper and buddybox storage tests pass, except tests still depending
on launcher workspace projection may fail until Task 4.

## Task 3: Bind The Runtime Broker To Shared State

**Files:**

- Modify: `tools/launcher/runtime_broker.sh`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `tests/test_runtime_broker.py`

- [ ] **Step 1: Export state root before broker Python starts**

In `tools/launcher/runtime_broker.sh`, run broker lifecycle commands with:

```text
BUDDYSWITCH_STATE_ROOT="${BUDDYSWITCH_SHARED_ROOT}/state"
```

This must be in the environment before `python3 scripts/runtime_kernel/broker.py` imports
`runtime_files`.

- [ ] **Step 2: Refresh runtime roots inside dispatcher context**

In `scripts/runtime_kernel/dispatcher.py`, after `_runtime_server_env` updates environment variables,
call:

```python
runtime_files.refresh_runtime_roots_from_env()
```

On exit, restore the previous environment and call the same refresh function again.

- [ ] **Step 3: Report both workspace and state roots**

Update broker `ping` and `status` payloads to include:

```text
runtime_workspace_root
runtime_state_root
env_store_root
```

Use:

```text
runtime_workspace_root = Path(instance_record["workspace_dir"]).resolve(strict=False)
runtime_state_root = runtime_files.STATE_ROOT.resolve(strict=False)
env_store_root = runtime_files.STATE_ROOT.resolve(strict=False)
```

- [ ] **Step 4: Update broker tests**

Update `tests/test_runtime_broker.py` so live status expects:

```text
runtime_workspace_root == workspace_dir
runtime_state_root == shared_root/state
env_store_root == shared_root/state
```

- [ ] **Step 5: Run broker tests**

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py -q
```

Expected after this task: broker status and broker-routed env.tool state writes use `shared/state`.

## Task 4: Remove Workspace State And Buddybox Projections

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `tests/test_clean_runtime_environment.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Stop declaring runtime object paths as workspace-managed outputs**

In `tools/launcher/workspace.sh`, remove these from workspace-managed path lists:

```text
buddyswitch/objects/tracks
buddyswitch/objects/tasks
buddyswitch/objects/artifacts
buddyswitch/objects/messages
buddyswitch/objects/comments
buddyswitch/local/buddybox/<active_buddy>
```

The state root owns those paths now.

- [ ] **Step 2: Retire state projection installation**

Remove calls that create symlinks from workspace paths into shared state:

```text
buddyswitch_workspace_install_state_projections
buddyswitch_workspace_projected_state_paths
```

Keep the runtime workspace sparse checkout focused on scripts, manifest, env profiles, and framework contracts.

- [ ] **Step 3: Add data-safe cleanup for old projections**

Add a launcher helper that runs during runtime surface sync:

```text
buddyswitch_workspace_cleanup_stale_state_projections
```

Required behavior:

- If `workspace/buddyswitch/objects` is a symlink or contains symlink children pointing into `shared/state`, remove only the workspace symlink path.
- If `workspace/buddyswitch/objects` is a real directory with JSON files, copy files into the matching `shared/state/buddyswitch/objects/**` path when the target file is absent, then remove the workspace directory.
- If both source and target files exist with different content, stop with a clear error and do not delete either file.
- Apply the same rules to `workspace/buddyswitch/local/buddybox/<buddy>` and `shared/state/buddyswitch/local/buddybox/<buddy>`.

- [ ] **Step 4: Keep project source projection**

Do not remove `projects/app`. It remains the live shared source projection and still follows each
buddy's project access profile.

- [ ] **Step 5: Run workspace tests**

Run:

```bash
python3 -m pytest tests/test_clean_runtime_environment.py tests/test_buddyswitch_launcher.py -q
```

Expected after this task: fresh and stale runtime workspaces no longer expose objects or buddybox storage.

## Task 5: Generate A Clean Product Codex Permission Profile

**Files:**

- Modify: `tools/launcher/codex_config.py`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Disable sandbox escalation prompts for product runtime**

Change product-session approval rendering so generated config contains:

```text
sandbox_approval = false
```

Keep these disabled:

```text
rules = false
mcp_elicitations = false
request_permissions = false
skill_approval = false
```

- [ ] **Step 2: Keep root read only as a Codex execution baseline**

Generate filesystem entries around this shape:

```toml
[permissions.buddyswitch-runtime.filesystem]
"/" = "read"
"/path/to/instance/workspace" = "read"
"/path/to/project/workspace" = "read"  # pm/design/test/market
"/path/to/project/workspace" = "write" # dev
"/path/to/instance/home" = "write"
"/path/to/instance/codex-home" = "write"
"/path/to/instance/xdg-config" = "write"
"/tmp" = "write"
"/path/to/shared/state" = "none"
"/path/to/source/repo" = "none"
```

Do not use workspace child denies for `buddyswitch/objects` or active buddybox as the primary
strategy. Those paths should not exist in the visible workspace after Task 4. The explicit state-root
and source-repo protections are still required because `"/" = "read"` remains the Codex execution
baseline.

- [ ] **Step 3: Keep broker socket access**

Preserve the existing Unix socket allowlist behavior:

```toml
[permissions.buddyswitch-runtime.network]
enabled = true
mode = "full"
unix_sockets = { "/path/to/runtime-broker.sock" = "allow" }
```

- [ ] **Step 4: Update launcher config tests**

Update tests so they assert the target behavior, not the old shape:

- no reliance on broad root read plus visible workspace child denies;
- no `buddyswitch/objects` workspace deny dependency;
- no active buddybox direct write grant;
- no sandbox approval escalation;
- project access matrix unchanged;
- state root blocked;
- source repo blocked.

- [ ] **Step 5: Run config tests and Codex sandbox smoke**

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
```

On macOS with Codex CLI available, the sandbox smoke in `tests/test_clean_runtime_environment.py`
must also pass:

```bash
python3 -m pytest tests/test_clean_runtime_environment.py -q
```

The expected profile may keep `"/" = "read"` because current Codex macOS sandbox behavior requires it
for basic shell execution. The acceptance criteria are that the visible workspace has no denied
runtime-state projections, source/state roots are explicitly protected, and sandbox escalation is
disabled.

## Task 6: Update Context And Buddybox Descriptions

**Files:**

- Modify: `scripts/env/tools/context/service.py`
- Modify: `scripts/env/domain/buddybox_workspace.py`
- Modify: `scripts/env/tools/buddybox/service.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Make context describe tool routes, not direct storage paths**

Update context source descriptions so product objects are described as env-tool-backed runtime state.
The host-visible guidance must point to:

```text
track.open
artifact.get
task.get/list
message.list
comment.list
buddybox.read/list/write/delete by logical_name
```

Do not instruct the host to read or edit `buddyswitch/objects/**` or
`buddyswitch/local/buddybox/**`.

- [ ] **Step 2: Keep buddybox private state fields accurate**

Ensure buddybox responses still include:

```text
owner_scope = active_buddy
visibility = active_buddy_private
product_readable = false
cross_buddy_readable = false
mutated_product_objects = []
logical_name = <relative logical name>
```

- [ ] **Step 3: Run context and buddybox tests**

Run:

```bash
python3 -m pytest tests/test_host_decision_surface_product_mode.py tests/test_buddybox_env_tool.py -q
```

Expected after this task: context and buddybox feedback align with the clean workspace contract.

## Task 7: Update Env Tool Integration Tests For State Root

**Files:**

- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_task_env_tool.py`
- Modify: `tests/test_message_env_tool.py`
- Modify: `tests/test_comment_env_tool.py`
- Modify: `tests/runtime_root_test_helper.py`

- [ ] **Step 1: Keep unit-style runtime tests isolated**

`RuntimeWorkspaceTestMixin` may continue using one temporary root for both workspace and state in
unit-style tests. Add an explicit helper name for this mode so it is not confused with product
launcher behavior:

```text
self.runtime_root = isolated test state root
```

- [ ] **Step 2: Add product-style broker tests where root separation matters**

For behavior that depends on clean runtime environment, use the product-style setup:

```text
shared_root/
  state/
  instances/<id>/workspace/
  project/workspace/
```

Do not convert every object repo unit test to product-style roots. Use product-style roots for
host-visible workspace and broker tests only.

- [ ] **Step 3: Update end-to-end assertions**

In `tests/test_env_layer_end_to_end.py`, add assertions that object files created during the flow are
under the state root used by the test setup and not under the host-visible workspace in product-style
coverage.

- [ ] **Step 4: Run env tool tests**

Run:

```bash
python3 -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_comment_env_tool.py \
  -q
```

Expected after this task: existing tool behavior remains intact and new product-style assertions pass.

## Task 8: Remove Residue And Prompt Workarounds

**Files:**

- Modify only files that still contain active old-contract residue found by the scan.

- [ ] **Step 1: Scan for retired projection code**

Run:

```bash
rg -n "buddyswitch_workspace_install_state_projections|buddyswitch_workspace_projected_state_paths|workspace/buddyswitch/objects|buddyswitch/local/buddybox/.+workspace" \
  tools scripts tests
```

Expected: no active references that preserve workspace projection as a runtime contract.

- [ ] **Step 2: Scan for sandbox escalation expectations**

Run:

```bash
rg -n "sandbox_approval = true|sandbox_approval.*true" \
  tools scripts tests
```

Expected: no product-session implementation or tests expect sandbox escalation.

- [ ] **Step 3: Scan for prompt-side workaround text**

Run:

```bash
rg -n "do not run rg|exclude buddyswitch/objects|retry without sandbox|always use rg --glob|command blacklist|phrase-to-tool" \
  tools/launcher/assets/buddies buddyswitch/skills scripts \
  -g '!tests/**'
```

Expected: no matches.

- [ ] **Step 4: Remove or rewrite active residue**

For each active match:

- remove it if it only preserves the old workspace projection contract;
- rewrite it to point to env-tool-backed runtime state when it is user-facing context;
- keep historical docs unchanged unless they are imported as active runtime guidance.

## Task 9: Full Verification

**Files:** none

- [ ] **Step 1: Run focused clean runtime suite**

Run:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_runtime_broker.py \
  tests/test_buddybox_env_tool.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run runtime env tool suite**

Run:

```bash
python3 -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_layer_boundaries.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_comment_env_tool.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run launcher suite**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: PASS.

- [ ] **Step 4: Run residue scans**

Run the scans from Task 8.

Expected: no active implementation or test residue for workspace state projection, sandbox
escalation, or prompt-side command workaround.

- [ ] **Step 5: Manual product-session smoke**

Start a fresh product instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

Inside the launched runtime workspace, run:

```bash
python3 scripts/env/client.py context summarize
rg --files
git status --short --untracked-files=all -- .
python3 scripts/env/client.py buddybox write --payload '{"logical_name":"smoke/clean-runtime.txt","content":"ok"}'
python3 scripts/env/client.py buddybox read --logical-name smoke/clean-runtime.txt
```

Expected:

- no permission prompt asks to retry without sandbox;
- `rg --files` exits cleanly;
- `git status` has no permission warning;
- context and buddybox commands succeed through the broker;
- `buddyswitch/objects` and `buddyswitch/local/buddybox/pm` are not ordinary workspace storage paths.

## Definition Of Done

- All tests in Task 9 pass or platform-specific Codex sandbox tests are skipped for documented platform reasons.
- Fresh product runtime workspaces do not expose runtime object or buddybox storage trees.
- Runtime broker stores product objects and buddybox private files under `shared/state`.
- Generated product Codex config explicitly protects source/state roots and does not enable sandbox escalation prompts.
- Dev/non-dev source access contracts are unchanged.
- No AGENTS, skill, or sub-agent prompt workaround is required for normal exploration commands.
- The final implementation report lists changed files, verification commands, and any platform-specific skipped checks.
