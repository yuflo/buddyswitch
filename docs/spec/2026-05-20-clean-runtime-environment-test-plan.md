# Clean Runtime Environment Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` when implementing the tests. Tests must be written from the functional requirements below before runtime implementation changes. Do not write tests that merely match the current implementation shape.

**Goal:** Prove BuddySwitch product sessions present a clean Codex-visible runtime environment where normal host exploration does not hit denied runtime state, while broker-owned state and buddybox private data remain available through env tools.

**Architecture:** Tests cover generated permission profiles, launcher workspace shape, broker-routed env.tool behavior, buddybox privacy, stale projection cleanup, and host-visible shell behavior. Assertions start from user-visible product requirements: no permission prompt loops, no direct runtime-state filesystem leakage, no weakened source permissions, and no prompt-side workaround.

**Tech Stack:** `pytest`, Python `unittest`, launcher shell helpers, temporary BuddySwitch shared roots, broker-routed env.tool calls, Codex CLI `codex sandbox macos` smoke tests when available, `rg`, `git status`, and static scans.

---

## Confirmed Task Target

The task is a forward repair of the runtime environment contract, not a transition patch.

The current key issue is:

```text
BuddySwitch shows runtime paths in the ordinary workspace while the sandbox denies those paths.
Codex runs normal exploration commands, receives Operation not permitted, then asks to retry outside the sandbox.
```

The repair must make these three boundaries agree:

```text
visible workspace = safe for ordinary host exploration
sandbox profile = no prompt loop for expected boundary failures
env tools = only supported access route for runtime state and buddybox private data
```

## Non-Negotiable Test Principles

- Tests must be functional and host-visible, not implementation-shape-only.
- Tests must fail against the current broken behavior before implementation.
- Tests must prove ordinary commands such as `rg --files`, `rg -n`, and `git status` are safe from the runtime workspace.
- Tests must prove runtime state still works through env tools after removing workspace projections.
- Tests must not pass by teaching `rg` to exclude special paths.
- Tests must not add or assert long AGENTS instructions, command blacklists, or phrase routers.
- Tests must not weaken runtime object privacy, buddybox privacy, or project source access controls.

## Functional Requirements

R1. A fresh product runtime workspace contains only host-visible runtime files that are safe for ordinary read-only exploration.

R2. `buddyswitch/objects/**` is not present as a traversable directory or symlink in the runtime workspace.

R3. Active-buddy buddybox storage is not exposed as an ordinary workspace directory that sub-agents are expected to locate through `rg`, `find`, or `git status`.

R4. Broker-owned product objects are written under the runtime state root, not under the host-visible workspace root.

R5. Buddybox files are read, written, listed, and deleted through `buddybox` env tools using `logical_name`.

R6. `context.summarize`, `context.get`, `track`, `task`, `artifact`, `message`, `comment`, and `buddybox` tools still work through the runtime broker after state is moved out of the visible workspace.

R7. Generated Codex product-session config does not rely on broad root read plus visible denied child paths as the runtime boundary. If current Codex requires `"/" = "read"` for basic command execution, the clean boundary must instead come from an ordinary workspace with no runtime-state projections, explicit source/state protections, and disabled sandbox escalation.

R8. Generated Codex product-session config does not ask the user to retry expected sandbox failures outside the sandbox.

R9. Dev can still write `projects/app`; PM, Design, Test, and Market can still read but not write `projects/app`.

R10. Source checkout, launcher internals, tests, docs, and runtime state roots remain protected from product-session writes.

R11. Existing runtime workspaces with old `buddyswitch/objects/**` and `buddyswitch/local/buddybox/**` projections are cleaned or migrated without losing runtime object data.

R12. Root guidance stays short. The fix must not require new AGENTS command blacklists or sub-agent prompt rules to avoid `rg --files`.

## Risk Model

Primary risks:

- Permission prompt loop remains because a denied path is still visible under the workspace.
- Env tools stop finding state because object roots moved out of the workspace without broker binding.
- Buddybox private files become product-readable or cross-buddy-readable during the move.
- Project source permissions regress and non-dev buddies gain write access.
- Tests pass by encoding current helper names instead of proving host-visible behavior.
- Stale symlink cleanup deletes shared state targets instead of only removing visible projections.
- `sandbox_approval` remains enabled and expected sandbox failures still interrupt the user.
- A prompt or AGENTS workaround is added instead of a runtime contract fix.

Testing rules:

- Positive runtime tests assert response fields and persisted files in the state root.
- Negative tests assert both rejection feedback and unchanged state.
- Host-visible tests assert command exit status, stdout/stderr, and absence of `Operation not permitted`.
- Permission tests parse generated TOML and run at least one Codex sandbox smoke when available.
- Static scans only enforce architectural residue; they do not replace runtime behavior tests.

## Test Matrix

| ID | Level | Requirement | File | Main assertion |
| --- | --- | --- | --- | --- |
| C1 | Config | R7/R8/R10 | `tests/test_buddy_env_sandbox.py` | Product permission profile has no visible denied workspace child dependency, keeps protected roots blocked, and disables sandbox escalation prompts |
| C2 | Config | R9/R10 | `tests/test_env_layer_boundaries.py` | Dev project workspace is writable; non-dev project workspace is read-only; state root and source checkout are not writable |
| W1 | Launcher workspace | R1/R2/R3 | `tests/test_clean_runtime_environment.py` | Fresh runtime workspace has no `buddyswitch/objects` tree and no active buddybox storage tree |
| W2 | Launcher cleanup | R11 | `tests/test_clean_runtime_environment.py` | Old state projections are removed from workspace without deleting files under shared state root |
| H1 | Host visible | R1/R2/R3/R8 | `tests/test_clean_runtime_environment.py` | `rg --files`, `rg -n`, and `git status --short --untracked-files=all` from runtime workspace do not emit `Operation not permitted` |
| S1 | Sandbox smoke | R1/R7/R8 | `tests/test_clean_runtime_environment.py` | `codex sandbox macos --permissions-profile buddyswitch-runtime rg --files` succeeds without sandbox-denial noise |
| B1 | Broker state | R4/R6 | `tests/test_runtime_broker.py` | Broker status reports distinct workspace and state roots; state root is under `shared/state` |
| B2 | Env tool e2e | R4/R6 | `tests/test_env_layer_end_to_end.py` | Track/artifact/message/comment/task object files are created in state root, not runtime workspace |
| BB1 | Buddybox | R3/R5 | `tests/test_buddybox_env_tool.py` | Buddybox lifecycle works through env tools and persists outside the ordinary workspace search surface |
| BB2 | Buddybox privacy | R5/R10 | `tests/test_buddybox_env_tool.py` | Cross-buddy, absolute path, traversal, and symlink escape attempts reject and leave state unchanged |
| CTX1 | Context | R4/R5/R6 | `tests/test_host_decision_surface_product_mode.py` | Context surfaces env-tool routes and does not imply direct file access to runtime objects or buddybox |
| D1 | Bitter alignment | R12 | `tests/test_clean_runtime_environment.py` | Runtime fix does not add AGENTS command blacklists or prompt rules for `rg`, `find`, or `git status` |

## Detailed Test Requirements

### C1: Product Permission Profile Is Clean

**Functional requirement:** Product sessions must not rely on broad host reads plus denied child paths inside the visible workspace.

**Setup:** Generate a profile with `tools/launcher/codex_config.py` for `pm` and `dev`.

**Assertions:**

- `default_permissions = "buddyswitch-runtime"` is present.
- `[permissions.buddyswitch-runtime.filesystem]` exists.
- If the root filesystem entry is `read`, no `workspace/buddyswitch/objects` or active buddybox workspace child deny is required for product correctness.
- The source checkout path is not writable.
- The shared state root is not readable or writable through ordinary filesystem permissions.
- `project_workspace_dir` is `read` for `pm` and `write` for `dev`.
- Active broker socket is allowlisted when provided.
- `sandbox_approval = false` appears in the generated approval policy.
- Active buddybox workspace is not granted as a direct filesystem write root.

**Failure mode caught:** Reintroducing the old combination of visible workspace projections, workspace child denies, active buddybox direct write grants, or sandbox escalation prompts.

### W1: Fresh Runtime Workspace Has No Hidden Denied Tree

**Functional requirement:** A clean runtime workspace should not contain visible paths that ordinary host commands cannot traverse.

**Setup:** Start or simulate a product instance workspace through launcher workspace helpers.

**Assertions:**

- `workspace/buddyswitch/objects` does not exist and is not a symlink.
- `workspace/buddyswitch/local/buddybox/<active_buddy>` does not exist and is not a symlink.
- `workspace/scripts/env/client.py`, `workspace/scripts/runtime_kernel/broker.py`, `workspace/scripts/turn_runtime.py`, `workspace/buddyswitch/manifest.toml`, and `workspace/framework/contracts/pm.md` exist.
- `workspace/projects/app` still resolves to the shared project workspace.

**Failure mode caught:** Keeping the old state projection while changing only config or prompt text.

### W2: Stale Projection Cleanup Is Data-Safe

**Functional requirement:** Existing users with old projections must not lose runtime object data.

**Setup:**

- Create `shared/state/buddyswitch/objects/tracks/track-old.json`.
- Create workspace symlinks under `workspace/buddyswitch/objects/tracks` pointing at that state path.
- Run the runtime workspace sync/ensure path.

**Assertions:**

- The workspace projection path is gone.
- `shared/state/buddyswitch/objects/tracks/track-old.json` still exists with unchanged content.
- If workspace contains a real non-symlink `buddyswitch/objects` directory with files, the sync migrates those JSON files into `shared/state/buddyswitch/objects/**` before removing the visible directory.

**Failure mode caught:** `rm -rf` deleting the symlink target or abandoning pre-existing local runtime data.

### H1: Ordinary Host Exploration Is Quiet

**Functional requirement:** Codex can orient itself with normal commands without permission prompt loops.

**Setup:** Use a clean runtime workspace after W1.

**Commands:**

```bash
rg --files
rg -n "context|buddybox|track" .
git status --short --untracked-files=all -- .
```

**Assertions:**

- Exit status is `0` for `rg --files`.
- `rg -n` exits `0` when it finds matches or `1` when it finds no matches; neither case may include `Operation not permitted`.
- `git status` exits `0`.
- stderr for all commands does not include `Operation not permitted`, `Permission denied`, or `retry without sandbox`.

**Failure mode caught:** Tests that only inspect TOML while ordinary commands still fail.

### S1: Codex Sandbox Smoke Covers The Real Host Boundary

**Functional requirement:** The generated Codex permission profile must work in the same command-execution layer that previously prompted.

**Setup:** On macOS with Codex CLI available, generate a product profile, create a clean runtime workspace, and run:

```bash
CODEX_HOME="$codex_home" codex sandbox macos \
  --permissions-profile buddyswitch-runtime \
  --cd "$workspace" \
  /bin/zsh -lc 'rg --files >/tmp/buddyswitch-rg-files.txt && git status --short --untracked-files=all -- . >/tmp/buddyswitch-git-status.txt'
```

**Assertions:**

- Command exits `0`.
- stderr has no `Operation not permitted`.
- stderr has no sandbox approval or retry wording.

**Skip rule:** Skip only when platform is not Darwin or Codex CLI is unavailable.

### B1/B2: Runtime State Still Works Through Broker

**Functional requirement:** Moving state out of the visible workspace must not break product collaboration tools.

**Setup:** Start the runtime broker with an instance under `shared/instances/<id>` and workspace under `shared/instances/<id>/workspace`.

**Assertions:**

- Broker `status` returns:
  - `runtime_root` or `runtime_workspace_root` equal to the instance workspace.
  - `env_store_root` or `runtime_state_root` equal to `shared/state`.
- `track.create` writes `shared/state/buddyswitch/objects/tracks/<track_id>.json`.
- `artifact.create_revision` writes `shared/state/buddyswitch/objects/artifacts/<artifact_id>.json`.
- `message.send`, `comment.add`, and `task.create` write under `shared/state/buddyswitch/objects/**`.
- None of those actions create `workspace/buddyswitch/objects/**`.

**Failure mode caught:** Env tools accidentally continuing to use workspace root as storage.

### BB1/BB2: Buddybox Is Tool-First And Private

**Functional requirement:** Buddybox remains usable and private without being normal workspace storage.

**Setup:** Use broker-routed `buddybox.write`, `buddybox.read`, `buddybox.list`, and `buddybox.delete`.

**Assertions:**

- `buddybox.write --logical-name coordination/a-log.md` succeeds.
- Persisted file exists under runtime state/private root for the active buddy.
- `workspace/buddyswitch/local/buddybox/<active_buddy>/coordination/a-log.md` does not exist.
- `buddybox.read --logical-name coordination/a-log.md` returns body content.
- `buddybox.list --recursive` returns the logical name.
- Another buddy cannot read or list the active buddy file through direct logical-name tricks.
- Absolute paths, `..`, buddy-prefixed logical names, and symlink escapes reject without mutation.

**Failure mode caught:** Replacing tool-backed privacy with direct filesystem access.

### CTX1: Context Does Not Advertise Direct Runtime Paths As Access Routes

**Functional requirement:** Host discovery should point to env tools, not to hidden storage paths.

**Assertions:**

- `context.summarize` includes tool affordances for `track`, `artifact`, `task`, `message`, `comment`, and `buddybox`.
- Buddybox description states active-buddy private, not product-readable, not cross-buddy-readable.
- Context source metadata may name logical storage classes, but it must not instruct the host to `cat`, `rg`, or edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`.

**Failure mode caught:** Moving storage while leaving context guidance that encourages direct file access.

### D1: No Prompt-Side Workaround

**Functional requirement:** The fix must obey `docs/bitter` by repairing runtime/tool layers.

**Static scan:**

```bash
rg -n "do not run rg|exclude buddyswitch/objects|retry without sandbox|always use rg --glob|command blacklist|phrase-to-tool" \
  tools/launcher/assets/buddies buddyswitch/skills scripts
```

**Assertion:** No matches in active AGENTS, skills, or runtime code.

## Required Verification Commands

Focused verification:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_runtime_broker.py \
  tests/test_buddybox_env_tool.py \
  -q
```

Broader runtime verification:

```bash
python3 -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_layer_boundaries.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

Residue scan:

```bash
rg -n "buddyswitch_workspace_install_state_projections|buddyswitch_workspace_projected_state_paths|sandbox_approval = true" \
  tools scripts tests \
  -g '!tests/fixtures/**'
```

Expected result: no active implementation or test expectation keeps the old projected-state contract or sandbox escalation contract.

## Definition Of Done For Testing

- The test suite contains failing-first coverage for the observed permission prompt path.
- Tests prove ordinary exploration commands are quiet from the runtime workspace.
- Tests prove env tools still mutate and read runtime state through the broker.
- Tests prove buddybox remains tool-backed and private.
- Tests prove dev/non-dev project access contracts are unchanged.
- Tests prove no AGENTS or skill prompt workaround was added.
