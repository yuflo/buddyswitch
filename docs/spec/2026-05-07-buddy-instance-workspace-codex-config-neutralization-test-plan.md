# Buddy Instance Workspace Codex Config Neutralization Test Plan

**Goal:** Verify that launcher-managed product buddy instances use only the instance `CODEX_HOME/config.toml` as the effective Codex permission source, and cannot be shadowed by repo-tracked workspace `.codex/config.toml`.

**Testing Principle:** Tests must start from product requirements and observable behavior. Do not write tests around a private helper name just to make a patch look covered. The main proof is the launched instance state: workspace project config absent, instance user config present and permission-complete, and development checkout config untouched.

---

## Functional Requirements Under Test

FR1. A product instance workspace must not retain `.codex/config.toml` because Codex project config can override launcher-managed user config.

FR2. `instance start --buddy <buddy>` must neutralize workspace project config after the execution worktree is created and before Codex is launched.

FR3. `instance open <instance-id>` must neutralize stale workspace project config in an existing instance before Codex is launched.

FR4. Launcher-managed `${instance_root}/codex-home/config.toml` must remain present and complete after neutralization.

FR5. Neutralization must be product-instance scoped and must not delete or rewrite the source checkout `.codex/config.toml`.

FR6. Neutralization must be idempotent: repeated start/open preparation must succeed whether workspace `.codex/config.toml` exists or is already absent.

FR7. Neutralization must not remove runtime workspace artifacts unrelated to Codex project config, including `AGENTS.md`, `.agents/skills`, runtime state projections, `runs/raw`, browser files, and guardrail hooks.

FR8. The implementation must not replace the removed workspace config with a second full managed config copy. Product mode should have one managed Codex permission source.

FR9. Stale workspace config values such as `approval_policy = "on-request"` and `sandbox_mode = "workspace-write"` must not survive in the product workspace config layer.

FR10. Existing env profile sandbox guarantees must remain unchanged: non-dev buddies still do not receive project write access, and dev still receives only the intended project write access.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01, TG-02 | `workspace/.codex/config.toml` does not exist after product start/open |
| FR2 | TG-01 | `instance start --buddy pm` launches and captures product workspace with no project config |
| FR3 | TG-02 | pre-seeded stale workspace project config is gone after `instance open` |
| FR4 | TG-01, TG-02, TG-04 | `codex-home/config.toml` contains runtime permission profile, broker socket allowlist, and MCP approve mode |
| FR5 | TG-03 | repo-root `.codex/config.toml` content is unchanged after non-instance launch |
| FR6 | TG-02 | repeated open succeeds and leaves project config absent |
| FR7 | TG-01, TG-02 | existing lifecycle assertions for AGENTS, skills, state paths, browser profile, auth symlink, and hooks still pass |
| FR8 | TG-05 | source search confirms no workspace config copy path recreates `.codex/config.toml` |
| FR9 | TG-02, TG-05 | stale `on-request` fixture is removed; search only finds source default or negative fixtures |
| FR10 | TG-04 | `tests/test_buddy_env_sandbox.py` still passes |

## Test Data

Use product-shaped launch commands:

```bash
./buddyswitch-codex instance start --buddy pm debug prompt-input "Draft the onboarding PRD"
./buddyswitch-codex instance open inst-pm-existing-config debug prompt-input "continue"
```

Use stale project config fixture:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
```

Use expected launcher-managed user config signals:

```toml
default_permissions = "buddyswitch-runtime"
approval_policy = { granular = { sandbox_approval = true, rules = false, mcp_elicitations = false, request_permissions = false, skill_approval = false } }
default_tools_approval_mode = "approve"
unix_sockets = { "<runtime-broker.sock>" = "allow" }
```

## Test Groups

### TG-01: Product Instance Start Removes Workspace Project Config

**Purpose:** Prove a newly started buddy instance cannot inherit the repo-tracked project config layer.

**Scenario:**

1. Start a PM instance through the public launcher using fake Codex, fake Chrome, and the existing capture harness.
2. Read the captured `instance_id`, `workspace_dir`, and `codex_home`.
3. Assert `workspace/.codex/config.toml` is absent.
4. Assert `codex-home/config.toml` exists and satisfies `_assert_codex_automation_config`.
5. Keep existing assertions for runtime AGENTS, active skills, broker socket, browser profile, auth symlink, instance lifecycle, and no legacy shared workspace.

**Primary test:**

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

**Expected proof:**

- The test passes.
- `workspace/.codex/config.toml` is absent.
- `codex-home/config.toml` contains the managed permission profile and broker socket allowlist.

### TG-02: Product Instance Open Removes Stale Workspace Project Config

**Purpose:** Prove existing instances are repaired before Codex launch, not only freshly created instances.

**Scenario:**

1. Create an instance record and worktree with `_write_instance_record` and `_add_test_worktree`.
2. Pre-seed `workspace/.codex/config.toml` with the stale `on-request` fixture.
3. Open the instance through `./buddyswitch-codex instance open`.
4. Assert the stale workspace project config is absent.
5. Assert `codex-home/config.toml` remains complete.
6. Open the same instance a second time and assert the project config remains absent.

**Primary tests:**

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_instance_open_patches_existing_config_and_preserves_mcp_sections -q
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_instance_open_repatches_config_idempotently -q
```

If the exact idempotency test name differs, attach the repeated-open assertion to the existing test that already opens the same instance twice.

**Expected proof:**

- The first open removes stale project config.
- The second open still succeeds.
- No stale `approval_policy = "on-request"` remains in `workspace/.codex/config.toml` because that file is absent.

### TG-03: Development Checkout Config Is Preserved

**Purpose:** Prove the fix is product-instance scoped and does not damage the BuddySwitch development checkout.

**Scenario:**

1. Read repo-root `.codex/config.toml` before a non-instance launcher invocation.
2. Run a non-instance Codex launch through the public launcher with fake Codex.
3. Read repo-root `.codex/config.toml` afterward.
4. Assert the file exists and content is byte-for-byte unchanged.

**Primary test:**

```bash
pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTest::test_non_instance_launch_keeps_repo_project_codex_config -q
```

**Expected proof:**

- The repo project config still exists.
- Its content did not change.

### TG-04: Managed Permission Profile Still Works

**Purpose:** Prove neutralization did not weaken the existing env/tool-layer permission work.

**Scenario:**

1. Run launcher lifecycle tests that inspect generated `codex-home/config.toml`.
2. Run sandbox/profile tests that parse generated permission profiles for PM, Market, Design, Dev, and Test.
3. Confirm broker socket allowlist and MCP approve mode remain present.

**Primary command:**

```bash
pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py -q
```

**Expected proof:**

- All tests pass.
- Non-dev product configs still exclude project write roots.
- Dev product config still includes the shared project workspace write root.
- All product profile configs still exclude raw state and whole workspace write roots.

### TG-05: Source Search For Duplicate Config Truth

**Purpose:** Prove the implementation does not create a second managed workspace config source.

**Commands:**

```bash
rg -n 'workspace/.codex/config.toml|\\.codex/config.toml|approval_policy = "on-request"|sandbox_mode = "workspace-write"' tools/launcher tests docs/spec .codex
```

**Expected proof:**

- `.codex/config.toml` remains the development checkout default.
- Tests may contain stale config fixtures and assertions.
- `tools/launcher` contains removal/neutralization logic, not a second full managed workspace config writer.

## Manual Product Smoke

Run only after automated tests pass and local Codex is available:

```bash
./buddyswitch-codex instance start --buddy pm -- --version
```

Then inspect the newest PM instance:

```bash
find "$HOME/.codex-buddyswitch/instances" -maxdepth 4 -path '*/workspace/.codex/config.toml' -print
```

Expected output:

```text
```

No product instance workspace project config should print for the newly created PM instance.

Also inspect the managed user config:

```bash
rg -n 'default_permissions|request_permissions|unix_sockets|default_tools_approval_mode' "$HOME/.codex-buddyswitch/instances"/*/codex-home/config.toml
```

Expected proof:

- The new instance has `default_permissions = "buddyswitch-runtime"`.
- `request_permissions = false` is present inside granular approval policy.
- The runtime broker socket is allowlisted.
- Chrome DevTools MCP default tool approval mode is `approve`.

## Anti-Cheat Guardrails

- Do not assert that a private function was called; assert the product workspace state after public launcher commands.
- Do not make a test pass by changing fake Codex to ignore config. The fixture should inspect files produced before fake Codex receives control.
- Do not satisfy tests by copying the full managed config into workspace `.codex/config.toml`; that preserves duplicate config truth.
- Do not remove repo-root `.codex/config.toml`; development mode still uses it.
- Do not narrow tests to PM-only implementation details. PM is the reproduction path, but the requirement applies to product instances generally.

## Acceptance Criteria

- `instance start --buddy pm` leaves no `workspace/.codex/config.toml`.
- `instance open <instance-id>` removes stale `workspace/.codex/config.toml`.
- `codex-home/config.toml` remains permission-complete.
- Repo-root `.codex/config.toml` remains unchanged.
- `tests/test_buddyswitch_launcher.py` and `tests/test_buddy_env_sandbox.py` pass.
- Source search shows no second full managed workspace config writer.
