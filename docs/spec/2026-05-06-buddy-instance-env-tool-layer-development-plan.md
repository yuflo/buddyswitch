# Buddy Instance Env Tool Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executed BuddySwitch buddy environment layer so each buddy's filesystem, tool, state, and context capabilities are enforced by launcher/runtime behavior instead of prompt wording.

**Architecture:** Add compact per-buddy env profiles as the machine-readable source of truth. Launcher validates profiles and compiles them into Codex sandbox roots, runtime AGENTS projection checks, browser bootstrap behavior, active skills, and a local runtime broker. Host-facing `scripts/**` commands keep the existing prepare/persist CLI shape, but in product mode they become clients of the launcher-managed broker; the broker is the only product-mode writer of canonical BuddySwitch state.

**Tech Stack:** Bash launcher scripts, Python runtime scripts, JSON contracts/profiles, TOML manifest parsing, Unix domain socket broker, `unittest`/`pytest`, Codex workspace-write sandbox configuration.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout for this task. Keep all source, docs, and tests inside the `dev0210` worktree.

## Current Bottleneck

Buddy instances are currently separated mostly by static instructions. The runtime environment still grants too much shared write capability and product-mode `prepare`/`persist` still run in the host process as direct file writers. The first bottleneck is therefore an executed capability boundary: profile-derived sandbox roots plus a controlled runtime broker that accepts or rejects state/tool operations with explicit feedback.

## Confirmed Facts

- `docs/spec/2026-05-06-buddy-instance-env-tool-layer-design.md` defines the target boundary and stop condition.
- `buddyswitch/manifest.toml` has exactly five buddies: `market`, `pm`, `design`, `dev`, and `test`.
- `scripts/turn_runtime.py` already owns the public `prepare` and `persist` CLI names.
- `scripts/runtime_kernel/resolve.py` and `scripts/runtime_kernel/persist.py` currently wrap `turn_runtime.py` and are the natural place to grow broker-facing internals.
- `tools/launcher/codex_config.py` currently builds writable roots from shared root and git common dir, which violates the new design for product instances.
- `tools/launcher/workspace.sh` projects shared state into each instance workspace and projects live `projects/app` as a symlink to `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`.
- `tools/launcher/browser_cockpit.sh` already starts headed Chrome and registers `chrome-devtools-cockpit`.
- `tools/launcher/assets/buddies/*/AGENTS.md` are static runtime AGENTS templates and currently do not explain profile-enforced write boundaries.
- `scripts/env_tracks.py` and `scripts/env_artifacts.py` remain manual/debug APIs and must not become the product runtime permission path.

## Open Assumptions And Invalidators

- Assumption: Codex workspace-write denies writes to resolved symlink targets when the target path is not in `writable_roots`. If tests prove otherwise, replace the runtime `projects/app` symlink for non-dev buddies with an OS-level read-only projection before continuing.
- Assumption: product-mode `prepare` and `persist` can route through a Unix domain socket broker while keeping the existing host-facing CLI. If socket routing is unreliable under Codex sandboxing, replace the CLI prompt guidance with a different `scripts/**` runtime tool and remove product-mode use of the old direct CLI.
- Assumption: a broker-issued browser cockpit preflight token is enough for this first validated loop. If product acceptance still shows silent Market downgrade, add browser navigation trace capture as a follow-up, not in this first step.
- Assumption: git common dir write access is not required for buddy runtime sessions. If a verified Codex runtime failure proves it is required, add the minimal git common path through an explicit profile-derived option and prove it cannot write source or state.

## Verification Stop Condition

Stop only when these are proven by tests or manual probes:

- Every manifest buddy has a valid env profile.
- `instance start --buddy market` and `instance open inst-pm-example` validate the active buddy profile before mutating instance state.
- Non-dev generated Codex config excludes shared root, whole instance root, project root, project workspace, execution workspace root, and raw state root.
- Dev generated Codex config includes only project workspace in addition to common safe roots and still excludes raw state root.
- Non-dev buddies cannot write `projects/app` through the runtime symlink or resolved shared project target.
- Dev can write `projects/app`.
- Host product-mode `prepare`/`persist` route through the runtime broker and fail explicitly if the broker is unavailable.
- The broker enforces active instance, active buddy, run envelope, profile state capability, manifest artifact kinds, current-task-only task effects, PM-only track lifecycle, and valid handoff targets.
- Market persist rejects research artifacts without broker-issued browser evidence or broker-issued approved downgrade.
- Runtime `AGENTS.md` is validated against profile/contract content and is not used as the permission source.

## File Map

Create:

- `buddyswitch/env-profiles/market.json`
- `buddyswitch/env-profiles/pm.json`
- `buddyswitch/env-profiles/design.json`
- `buddyswitch/env-profiles/dev.json`
- `buddyswitch/env-profiles/test.json`
- `framework/contracts/buddy-env-profile.json`
- `scripts/env_profiles.py`
- `scripts/runtime_agents.py`
- `scripts/browser_evidence.py`
- `scripts/runtime_kernel/client.py`
- `scripts/runtime_kernel/broker.py`
- `tools/launcher/runtime_broker.sh`
- `tests/test_buddy_env_profiles.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_runtime_broker.py`
- `tests/test_market_browser_evidence.py`

Modify:

- `buddyswitch-codex`
- `tools/launcher/env.sh`
- `tools/launcher/workspace.sh`
- `tools/launcher/browser_cockpit.sh`
- `tools/launcher/codex_config.py`
- `tools/launcher/instance.sh`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`
- `scripts/turn_runtime.py`
- `scripts/runtime_kernel/resolve.py`
- `scripts/runtime_kernel/persist.py`
- `framework/contracts/persist-buddy-run.json`
- `framework/contracts/market.md`
- `framework/contracts/pm.md`
- `framework/contracts/design.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/browser-cockpit.md`
- `framework/docs/architecture-overview.md`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`
- `tests/test_turn_runtime.py`
- `tests/test_turn_integration.py`
- `tests/test_repo_consistency.py`

Preserve:

- `scripts/env_tracks.py` and `scripts/env_artifacts.py` as manual/debug APIs only.
- Active buddy skill materialization through `scripts/runtime_skills.py`.
- Existing public CLI names: `python3 scripts/turn_runtime.py prepare` and `python3 scripts/turn_runtime.py persist`.
- Existing canonical state object directories and JSON object shapes unless this plan explicitly changes a field.

## Target Profile Shape

The first profile schema is intentionally compact and not a generic permission DSL.

Each profile must use these top-level keys in this order:

```json
[
  "buddy_id",
  "contract_path",
  "project",
  "scratch",
  "filesystem_capability",
  "state_capability",
  "tool_capability",
  "context_projection"
]
```

Use these fixed profile field meanings:

- `project.visibility`: always `live`.
- `project.access`: `read-only` for `market`, `pm`, `design`, and `test`; `write` for `dev`.
- `scratch.root`: one of `runs/raw/market`, `runs/raw/pm`, `runs/raw/design`, `runs/raw/dev`, or `runs/raw/test`.
- `filesystem_capability.host_writable`: symbolic root labels compiled by launcher, not raw paths.
- `filesystem_capability.project_workspace`: `write` only for Dev, `read-only` for all other buddies.
- `filesystem_capability.raw_state`: always `broker-only`.
- `state_capability.artifact_kinds`: always `from-manifest`.
- `state_capability.task_effects`: always `["status", "summary"]`.
- `state_capability.track_effects`: `["create", "update", "advance", "archive"]` only for PM, `[]` for all other buddies.
- `state_capability.handoff_targets`: always `manifest-buddies`.
- `tool_capability.browser_cockpit`: `required` for Market, `available` for PM/Design/Dev/Test.
- `tool_capability.market_research_evidence`: `required` for Market, `not-required` for PM/Design/Dev/Test.
- `tool_capability.ordinary_web_fallback`: `user-approved-only` for Market, `available` for PM/Design/Dev/Test.
- `context_projection.agents_md`: always `from-profile-and-contract`.
- `context_projection.skills`: always `active-buddy-only`.

## Implementation Tasks

### Task 1: Add Env Profile Contract And Five Profiles

**Files:**

- Create: `framework/contracts/buddy-env-profile.json`
- Create: `buddyswitch/env-profiles/market.json`
- Create: `buddyswitch/env-profiles/pm.json`
- Create: `buddyswitch/env-profiles/design.json`
- Create: `buddyswitch/env-profiles/dev.json`
- Create: `buddyswitch/env-profiles/test.json`
- Test: `tests/test_buddy_env_profiles.py`

- [ ] **Step 1: Create the profile contract**

Create `framework/contracts/buddy-env-profile.json` with this exact baseline:

```json
{
  "contract_id": "buddy-env-profile",
  "contract_version": "2026-05-06",
  "top_level_key_order": [
    "buddy_id",
    "contract_path",
    "project",
    "scratch",
    "filesystem_capability",
    "state_capability",
    "tool_capability",
    "context_projection"
  ],
  "required_top_level_keys": [
    "buddy_id",
    "contract_path",
    "project",
    "scratch",
    "filesystem_capability",
    "state_capability",
    "tool_capability",
    "context_projection"
  ],
  "enums": {
    "project.visibility": ["live"],
    "project.access": ["read-only", "write"],
    "filesystem_capability.project_workspace": ["read-only", "write"],
    "filesystem_capability.raw_state": ["broker-only"],
    "state_capability.artifact_kinds": ["from-manifest"],
    "state_capability.handoff_targets": ["manifest-buddies"],
    "tool_capability.browser_cockpit": ["required", "available", "unavailable"],
    "tool_capability.market_research_evidence": ["required", "not-required"],
    "tool_capability.ordinary_web_fallback": ["available", "user-approved-only"],
    "context_projection.agents_md": ["from-profile-and-contract"],
    "context_projection.skills": ["active-buddy-only"]
  },
  "non_goals": [
    "generic permission DSL",
    "workflow engine",
    "raw state access for host process",
    "prompt-only permission source"
  ]
}
```

- [ ] **Step 2: Create Market profile**

Create `buddyswitch/env-profiles/market.json`:

```json
{
  "buddy_id": "market",
  "contract_path": "framework/contracts/market.md",
  "project": {
    "visibility": "live",
    "access": "read-only",
    "path": "projects/app"
  },
  "scratch": {
    "root": "runs/raw/market"
  },
  "filesystem_capability": {
    "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp"],
    "project_workspace": "read-only",
    "raw_state": "broker-only"
  },
  "state_capability": {
    "artifact_kinds": "from-manifest",
    "task_effects": ["status", "summary"],
    "track_effects": [],
    "handoff_targets": "manifest-buddies"
  },
  "tool_capability": {
    "browser_cockpit": "required",
    "market_research_evidence": "required",
    "ordinary_web_fallback": "user-approved-only"
  },
  "context_projection": {
    "agents_md": "from-profile-and-contract",
    "skills": "active-buddy-only"
  }
}
```

- [ ] **Step 3: Create PM profile**

Create `buddyswitch/env-profiles/pm.json`:

```json
{
  "buddy_id": "pm",
  "contract_path": "framework/contracts/pm.md",
  "project": {
    "visibility": "live",
    "access": "read-only",
    "path": "projects/app"
  },
  "scratch": {
    "root": "runs/raw/pm"
  },
  "filesystem_capability": {
    "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp"],
    "project_workspace": "read-only",
    "raw_state": "broker-only"
  },
  "state_capability": {
    "artifact_kinds": "from-manifest",
    "task_effects": ["status", "summary"],
    "track_effects": ["create", "update", "advance", "archive"],
    "handoff_targets": "manifest-buddies"
  },
  "tool_capability": {
    "browser_cockpit": "available",
    "market_research_evidence": "not-required",
    "ordinary_web_fallback": "available"
  },
  "context_projection": {
    "agents_md": "from-profile-and-contract",
    "skills": "active-buddy-only"
  }
}
```

- [ ] **Step 4: Create Design profile**

Create `buddyswitch/env-profiles/design.json`:

```json
{
  "buddy_id": "design",
  "contract_path": "framework/contracts/design.md",
  "project": {
    "visibility": "live",
    "access": "read-only",
    "path": "projects/app"
  },
  "scratch": {
    "root": "runs/raw/design"
  },
  "filesystem_capability": {
    "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp"],
    "project_workspace": "read-only",
    "raw_state": "broker-only"
  },
  "state_capability": {
    "artifact_kinds": "from-manifest",
    "task_effects": ["status", "summary"],
    "track_effects": [],
    "handoff_targets": "manifest-buddies"
  },
  "tool_capability": {
    "browser_cockpit": "available",
    "market_research_evidence": "not-required",
    "ordinary_web_fallback": "available"
  },
  "context_projection": {
    "agents_md": "from-profile-and-contract",
    "skills": "active-buddy-only"
  }
}
```

- [ ] **Step 5: Create Dev profile**

Create `buddyswitch/env-profiles/dev.json`:

```json
{
  "buddy_id": "dev",
  "contract_path": "framework/contracts/dev.md",
  "project": {
    "visibility": "live",
    "access": "write",
    "path": "projects/app"
  },
  "scratch": {
    "root": "runs/raw/dev"
  },
  "filesystem_capability": {
    "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp", "project-workspace"],
    "project_workspace": "write",
    "raw_state": "broker-only"
  },
  "state_capability": {
    "artifact_kinds": "from-manifest",
    "task_effects": ["status", "summary"],
    "track_effects": [],
    "handoff_targets": "manifest-buddies"
  },
  "tool_capability": {
    "browser_cockpit": "available",
    "market_research_evidence": "not-required",
    "ordinary_web_fallback": "available"
  },
  "context_projection": {
    "agents_md": "from-profile-and-contract",
    "skills": "active-buddy-only"
  }
}
```

- [ ] **Step 6: Create Test profile**

Create `buddyswitch/env-profiles/test.json`:

```json
{
  "buddy_id": "test",
  "contract_path": "framework/contracts/test.md",
  "project": {
    "visibility": "live",
    "access": "read-only",
    "path": "projects/app"
  },
  "scratch": {
    "root": "runs/raw/test"
  },
  "filesystem_capability": {
    "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp"],
    "project_workspace": "read-only",
    "raw_state": "broker-only"
  },
  "state_capability": {
    "artifact_kinds": "from-manifest",
    "task_effects": ["status", "summary"],
    "track_effects": [],
    "handoff_targets": "manifest-buddies"
  },
  "tool_capability": {
    "browser_cockpit": "available",
    "market_research_evidence": "not-required",
    "ordinary_web_fallback": "available"
  },
  "context_projection": {
    "agents_md": "from-profile-and-contract",
    "skills": "active-buddy-only"
  }
}
```

- [ ] **Step 7: Add profile contract tests**

Create `tests/test_buddy_env_profiles.py` with tests that load `buddyswitch/manifest.toml`, enumerate manifest buddies, and assert:

- exactly one profile exists for each manifest buddy;
- every profile file has the required top-level keys in the contract order;
- `buddy_id` matches both filename and manifest buddy id;
- `contract_path` exists;
- every non-dev profile has `project.access == "read-only"`;
- Dev profile has `project.access == "write"`;
- every scratch root matches its buddy-specific directory: `runs/raw/market`, `runs/raw/pm`, `runs/raw/design`, `runs/raw/dev`, or `runs/raw/test`;
- Market has browser/evidence required and user-approved ordinary fallback;
- PM is the only profile with non-empty `state_capability.track_effects`;
- every profile uses `raw_state == "broker-only"`.

Run:

```bash
python3 -m unittest tests.test_buddy_env_profiles -v
```

Expected now after implementation: all profile tests pass.

### Task 2: Add Profile Loader And Validator

**Files:**

- Create: `scripts/env_profiles.py`
- Modify: `tests/test_buddy_env_profiles.py`

- [ ] **Step 1: Implement `scripts/env_profiles.py`**

Add a small validator with these exact public symbols:

- `class EnvProfileError(ValueError)`: raised when a BuddySwitch env profile is missing or invalid.
- `env_profiles_root(root: Path | None = None) -> Path`: returns `repo_root / "buddyswitch" / "env-profiles"` when `root` is not provided.
- `env_profile_path(buddy_id: str, root: Path | None = None) -> Path`: validates the buddy id with the manifest safe-id pattern and returns `profiles_root / f"{buddy_id}.json"`.
- `load_env_profile(buddy_id: str, root: Path | None = None) -> dict[str, Any]`: reads the profile JSON object and raises `EnvProfileError` for missing files, invalid JSON, or non-object JSON.
- `validate_env_profile(profile: dict[str, Any], *, buddy_id: str, manifest: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]`: returns a normalized profile or raises `EnvProfileError`.
- `require_env_profile(buddy_id: str, *, manifest_path: Path = DEFAULT_MANIFEST, repo_root: Path | None = None) -> dict[str, Any]`: loads `buddyswitch/manifest.toml`, validates buddy membership, loads the profile, and returns the normalized profile.

Validation must be explicit and dependency-free. Do not add `jsonschema` or a generic schema engine. The validator should read `framework/contracts/buddy-env-profile.json` for fixed key order and enum lists, then enforce the buddy-specific rules listed in this plan.

- [ ] **Step 2: Add a CLI to `scripts/env_profiles.py`**

Support:

```bash
python3 scripts/env_profiles.py validate --buddy market
python3 scripts/env_profiles.py validate-all
python3 scripts/env_profiles.py show --buddy dev
```

Expected CLI behavior:

- invalid or missing profile exits non-zero with a message beginning `Env profile invalid:`;
- `validate-all` prints these five lines: `market: ok`, `pm: ok`, `design: ok`, `dev: ok`, and `test: ok`;
- `show` prints normalized profile JSON.

- [ ] **Step 3: Wire tests through the validator**

Update `tests/test_buddy_env_profiles.py` so profile tests use `env_profiles.require_env_profile()` rather than duplicating all validation in the test. Keep separate tests for observable profile matrix facts so the tests still describe product behavior.

Run:

```bash
python3 -m unittest tests.test_buddy_env_profiles -v
```

Expected: all tests pass and an intentionally corrupted temporary profile fixture fails with `EnvProfileError`.

### Task 3: Compile Profile Filesystem Capability Into Codex Config

**Files:**

- Modify: `tools/launcher/codex_config.py`
- Modify: `tools/launcher/env.sh`
- Create: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Replace blanket shared-root roots**

Change `tools/launcher/codex_config.py` so product-mode root generation no longer grants:

- `${BUDDYSWITCH_SHARED_ROOT}`;
- whole instance root;
- execution workspace root;
- `${BUDDYSWITCH_SHARED_ROOT}/project`;
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` except for Dev;
- `${BUDDYSWITCH_SHARED_ROOT}/state`;
- runtime state symlink paths under the execution workspace.

The new product-mode writable roots must be exactly:

- `BUDDYSWITCH_HOME`;
- `BUDDYSWITCH_CODEX_HOME`;
- `BUDDYSWITCH_XDG_CONFIG_HOME`;
- `${BUDDYSWITCH_WORKSPACE_DIR}/runs/raw/market`, `${BUDDYSWITCH_WORKSPACE_DIR}/runs/raw/pm`, `${BUDDYSWITCH_WORKSPACE_DIR}/runs/raw/design`, `${BUDDYSWITCH_WORKSPACE_DIR}/runs/raw/dev`, or `${BUDDYSWITCH_WORKSPACE_DIR}/runs/raw/test` for the active buddy;
- `/tmp`;
- `$TMPDIR` when present and safe;
- `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` only when `project.access == "write"`.

- [ ] **Step 2: Add explicit profile-driven CLI args**

Update `tools/launcher/codex_config.py` args:

```text
--config CONFIG_PATH
--repo-root REPO_ROOT
--shared-root SHARED_ROOT
--source-codex-home SOURCE_CODEX_HOME
--buddy BUDDY_ID
--instance-root INSTANCE_ROOT
--workspace-dir WORKSPACE_DIR
--project-workspace-dir PROJECT_WORKSPACE_DIR
--home INSTANCE_HOME
--codex-home INSTANCE_CODEX_HOME
--xdg-config-home INSTANCE_XDG_CONFIG_HOME
--temp-root TEMP_ROOT repeated
```

Use `scripts/env_profiles.py` to load and validate the profile for `--buddy`. Reject missing profile before writing `config.toml`.

- [ ] **Step 3: Keep config patch idempotence**

Preserve the existing managed top-level block, MCP approval patching, old managed-section stripping, and idempotent rewrite behavior. Only change the source of `writable_roots`.

- [ ] **Step 4: Update launcher config patch call**

In `tools/launcher/env.sh`, update `buddyswitch_patch_codex_config` to pass the new args when `BUDDYSWITCH_ACTIVE_BUDDY` or `BUDDYSWITCH_START_BUDDY` is set.

For non-instance development mode, keep a conservative local path that does not use env profiles and does not affect product instances. Product-mode paths must always require a valid profile.

- [ ] **Step 5: Add sandbox root tests**

Create `tests/test_buddy_env_sandbox.py` with table-driven assertions for each buddy. Parse the generated `config.toml` text and assert allowed and forbidden roots by canonical path.

Required cases:

- Market/PM/Design/Test exclude shared root, project root, project workspace, state root, execution workspace root, and instance root.
- Dev includes project workspace and excludes state root, shared root, project root, execution workspace root, and instance root.
- Every buddy includes instance home, instance codex-home, instance xdg-config, buddy scratch root, and safe temp root.
- Existing MCP server sections get `default_tools_approval_mode = "approve"` after patching.
- Missing profile makes `codex_config.py` exit `2` and leaves existing config text unchanged.

Run:

```bash
python3 -m unittest tests.test_buddy_env_sandbox -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_codex_config_patch_removes_prior_misnested_managed_settings_idempotently -v
```

Expected: root assertions match the profile matrix and config patch remains idempotent.

### Task 4: Validate Profile During Launcher Assembly

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/instance.sh`
- Create: `scripts/runtime_agents.py`
- Modify: `tools/launcher/assets/buddies/*/AGENTS.md`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add launcher profile validation helper**

In `tools/launcher/env.sh`, add:

```bash
buddyswitch_require_env_profile() {
  local buddy_id="$1"
  python3 "${BUDDYSWITCH_REPO_ROOT}/scripts/env_profiles.py" validate --buddy "${buddy_id}"
}
```

Call this before any instance mutation in:

- `start_locked_bootstrap`;
- `instance_open_locked_bootstrap`;
- any helper that validates an existing instance record before open.

Invalid profile must fail before creating or modifying:

- `${BUDDYSWITCH_SHARED_ROOT}/instances/inst-pm-example`;
- `${BUDDYSWITCH_SHARED_ROOT}/state`;
- `${BUDDYSWITCH_SHARED_ROOT}/project`;
- `${BUDDYSWITCH_CODEX_HOME}/config.toml`.

- [ ] **Step 2: Add runtime AGENTS validator**

Create `scripts/runtime_agents.py` with public function `validate_runtime_agents_template(*, buddy_id: str, template_path: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]`. It returns `{"ok": True, "buddy_id": buddy_id, "template_path": str(template_path)}` on success and raises `RuntimeAgentsError` with a concrete missing-boundary message on failure.

Validate the template contains:

- `# BuddySwitch Runtime Workspace`;
- active buddy id;
- `scripts/turn_runtime.py prepare`;
- `scripts/turn_runtime.py persist`;
- profile `project.access` wording;
- profile scratch root;
- raw state is broker-only;
- source write authority wording for Dev;
- source read-only and Dev handoff wording for non-dev;
- Market browser-native first execution and approved downgrade wording when Market profile requires it;
- receipt sections `Receipt` and `Summary`.

Add CLI:

```bash
python3 scripts/runtime_agents.py validate --buddy market --template tools/launcher/assets/buddies/market/AGENTS.md
python3 scripts/runtime_agents.py validate-all
```

- [ ] **Step 3: Update AGENTS templates**

Update all five runtime AGENTS templates under `tools/launcher/assets/buddies/market/`, `tools/launcher/assets/buddies/pm/`, `tools/launcher/assets/buddies/design/`, `tools/launcher/assets/buddies/dev/`, and `tools/launcher/assets/buddies/test/`.

Common required additions:

- `AGENTS.md` describes the environment but is not the permission source.
- `projects/app` is live shared product source.
- Allowed scratch root is exactly the active buddy directory: `runs/raw/market/`, `runs/raw/pm/`, `runs/raw/design/`, `runs/raw/dev/`, or `runs/raw/test/`.
- Raw BuddySwitch state is broker-only; do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- If a tool rejects a write or persist, do not route around it; report the rejection or hand off to the correct buddy.
- `prepare`/`persist` remain the CLI surface, but product mode routes them through the controlled runtime tool.

Buddy-specific additions:

- Market: browser cockpit is required, use `chrome-devtools-cockpit`, ordinary web fallback requires explicit user-approved downgrade, Market persist can reject missing browser evidence.
- PM: project source is read-only, PM owns track lifecycle only through `state_effects.track`.
- Design: project source is read-only, design output should hand off to Dev for source implementation.
- Dev: project source is writable, runtime scratch stays under `runs/raw/dev/`, state writes still go through persist.
- Test: project source, tests, fixtures, snapshots, and generated source under `projects/app` are read-only; failures should hand off to Dev rather than editing source.

- [ ] **Step 4: Validate templates during launcher preparation**

Update `buddyswitch_require_buddy_agents_template` or `buddyswitch_workspace_install_runtime_agents` so launch/open validates the template before copying it to the instance workspace. Failure must stop launch/open before Codex starts.

- [ ] **Step 5: Add launcher assembly tests**

Extend `tests/test_buddyswitch_launcher.py`:

- unknown buddy still fails before shared root mutation;
- missing env profile fails before shared root mutation;
- profile buddy mismatch fails before shared root mutation;
- `instance start --buddy market` validates Market profile, installs only Market skills, and records active instance metadata;
- `instance open inst-pm-example` revalidates profile and AGENTS before launching Codex;
- runtime `AGENTS.md` copied into workspace contains the profile boundary text for the active buddy.

Run:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
python3 -m unittest tests.test_repo_consistency -v
```

Expected: invalid profile cases are read-only failures; valid starts use profile-derived context.

### Task 5: Add Launcher-Managed Runtime Broker

**Files:**

- Create: `scripts/runtime_kernel/client.py`
- Create: `scripts/runtime_kernel/broker.py`
- Create: `tools/launcher/runtime_broker.sh`
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/instance.sh`
- Modify: `scripts/runtime_kernel/resolve.py`
- Modify: `scripts/runtime_kernel/persist.py`
- Modify: `scripts/turn_runtime.py`
- Create: `tests/test_runtime_broker.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`

- [ ] **Step 1: Define broker socket protocol**

Use one JSON request per Unix socket connection:

```json
{
  "protocol": "buddyswitch-runtime-broker/v1",
  "instance_id": "inst-pm-example",
  "active_buddy": "pm",
  "method": "prepare",
  "payload": {
    "text": "ordinary request"
  }
}
```

Persist request:

```json
{
  "protocol": "buddyswitch-runtime-broker/v1",
  "instance_id": "inst-pm-example",
  "active_buddy": "pm",
  "method": "persist",
  "payload": {
    "context": {},
    "result": {}
  }
}
```

Success response:

```json
{
  "ok": true,
  "payload": {}
}
```

Failure response:

```json
{
  "ok": false,
  "error": {
    "code": "E_RUNTIME_BROKER",
    "message": "human-readable rejection"
  }
}
```

- [ ] **Step 2: Implement broker server**

Create `scripts/runtime_kernel/broker.py` with CLI:

```bash
python3 scripts/runtime_kernel/broker.py serve \
  --socket "$BUDDYSWITCH_INSTANCE_ROOT/runtime/runtime-broker.sock" \
  --pid-file "$BUDDYSWITCH_INSTANCE_ROOT/runtime/runtime-broker.pid" \
  --instance-json "$BUDDYSWITCH_INSTANCE_ROOT/instance.json" \
  --manifest buddyswitch/manifest.toml
```

Server responsibilities:

- load instance JSON on every request;
- reject instance id mismatch;
- reject active buddy mismatch;
- validate env profile for active buddy;
- set `BUDDYSWITCH_RUNTIME_BROKER_MODE=server` while dispatching;
- set product env vars expected by `turn_runtime.py`;
- call `turn_runtime.prepare_turn_context()` for `prepare`;
- call `turn_runtime.persist_buddy_run()` for `persist`;
- serialize requests so there is no concurrent state mutation inside one instance broker;
- return `ok=false` JSON instead of crashing on validation failure.

- [ ] **Step 3: Implement broker client**

Create `scripts/runtime_kernel/client.py` with these exact public symbols:

- `class RuntimeBrokerError(RuntimeError)`: raised when the product-mode runtime broker is unavailable or rejects a request.
- `runtime_broker_socket_from_env() -> Path`: reads `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`, verifies it is non-empty, and returns the socket path.
- `request_runtime_broker(method: str, payload: dict[str, Any]) -> dict[str, Any]`: sends one JSON request to the broker and returns the decoded broker response.

Read:

- `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`;
- `BUDDYSWITCH_INSTANCE_ID`;
- `BUDDYSWITCH_ACTIVE_BUDDY`.

If any value is missing in product mode, raise an error with code `E_RUNTIME_BROKER_UNAVAILABLE`.

- [ ] **Step 4: Route product-mode CLI through broker**

Modify `scripts/turn_runtime.py`:

- In `_cmd_prepare`, if product session exists and `BUDDYSWITCH_RUNTIME_BROKER_MODE != "server"`, call broker client method `prepare` and print the broker payload.
- In `_cmd_persist`, if product session exists and `BUDDYSWITCH_RUNTIME_BROKER_MODE != "server"`, call broker client method `persist` and print the broker payload.
- If broker is unavailable, return `ok=false` with error code `E_RUNTIME_BROKER_UNAVAILABLE`.
- Keep non-product mode direct function behavior for unit tests and manual/debug development.

This removes the product-mode direct state write path. Do not keep an environment fallback that writes state directly when broker routing fails.

- [ ] **Step 5: Update runtime kernel wrappers**

Update `scripts/runtime_kernel/resolve.py` and `scripts/runtime_kernel/persist.py` so broker internals can call them without re-entering broker client routing. Keep the public wrapper names stable.

- [ ] **Step 6: Add launcher broker helper**

Create `tools/launcher/runtime_broker.sh` with these shell functions:

```bash
buddyswitch_runtime_broker_socket() {
  printf '%s/runtime/runtime-broker.sock\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_pid_file() {
  printf '%s/runtime/runtime-broker.pid\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}
```

Also add `buddyswitch_runtime_broker_ensure` and `buddyswitch_runtime_broker_stop`. `ensure` starts the server from `${BUDDYSWITCH_WORKSPACE_DIR}` after the execution worktree and instance record exist. It must export `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` for the Codex process. `stop` should terminate the pid file process when the instance is set inactive or deleted.

- [ ] **Step 7: Source broker helper in launcher**

In `buddyswitch-codex`, source `tools/launcher/runtime_broker.sh`.

Call `buddyswitch_runtime_broker_ensure` in:

- `start_locked_bootstrap` after instance activation and workspace projection;
- `instance_open_locked_bootstrap` after profile and workspace validation.

Pass `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` into `buddyswitch_run_codex` for active buddy sessions.

Call `buddyswitch_runtime_broker_stop` during inactive transition and instance deletion.

- [ ] **Step 8: Add broker tests**

Create `tests/test_runtime_broker.py`:

- broker prepare succeeds with matching instance/buddy and writes state from broker context;
- broker persist succeeds with matching instance/buddy and writes one run audit;
- request with wrong instance id is rejected;
- request with wrong active buddy is rejected;
- product-mode CLI with missing broker socket returns `ok=false` and does not write state;
- product-mode CLI with broker socket delegates and does not invoke direct write path in host process.

Run:

```bash
python3 -m unittest tests.test_runtime_broker -v
python3 -m unittest tests.test_turn_runtime -v
python3 -m unittest tests.test_turn_integration -v
```

Expected: broker is the only product-mode writer and existing non-product unit tests still exercise direct pure runtime functions.

### Task 6: Enforce Profile State Capability During Persist

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `framework/contracts/persist-buddy-run.json`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_runtime_broker.py`

- [ ] **Step 1: Load env profile during persist validation**

In `persist_buddy_run`, load `env_profiles.require_env_profile(active_buddy)` after active buddy is resolved. Pass the normalized profile into commit validation.

- [ ] **Step 2: Enforce profile state capability**

Extend `_validate_buddy_run_commit` or a focused helper to enforce:

- `state_capability.artifact_kinds == "from-manifest"` and artifact kind must be active buddy manifest kind;
- `state_capability.task_effects` allows only `status` and `summary`;
- task effects apply only to `context.current_task_id`;
- `state_capability.track_effects` allows track lifecycle only for PM;
- `state_capability.handoff_targets == "manifest-buddies"` and handoff target must be a manifest buddy;
- rejected commits fail before artifacts, tracks, tasks, runs, reservations, or instance bindings are modified.

Do not add local special cases for individual buddy names outside the profile matrix except where loading a specific profile is unavoidable.

- [ ] **Step 3: Extend persist contract for tool evidence**

Modify `framework/contracts/persist-buddy-run.json` to add `tool_evidence` to `commit_optional_keys`.

Do not require `tool_evidence` for PM/Design/Dev/Test. Market enforcement is profile-driven in Task 7.

- [ ] **Step 4: Add state capability tests**

Update runtime tests:

- PM `track.create`, `track.update`, `track.advance`, and `track.archive` succeed for valid prepared context.
- Market/Design/Dev/Test track lifecycle attempts are rejected before writes.
- unauthorized artifact kind is rejected before writes.
- task effect with unknown key is rejected before writes.
- task effect cannot target arbitrary task id.
- stale context and replayed run envelope are rejected before writes.
- handoff to unknown buddy is rejected before writes.

Run:

```bash
python3 -m unittest tests.test_turn_runtime -v
python3 -m unittest tests.test_turn_integration -v
```

Expected: profile and manifest together define state authority; no buddy can mutate state outside its active run envelope.

### Task 7: Add Browser Evidence Tool And Market Evidence Gate

**Files:**

- Create: `scripts/browser_evidence.py`
- Modify: `scripts/runtime_kernel/broker.py`
- Modify: `scripts/runtime_kernel/client.py`
- Modify: `scripts/turn_runtime.py`
- Modify: `framework/contracts/persist-buddy-run.json`
- Modify: `framework/contracts/market.md`
- Modify: `framework/docs/browser-cockpit.md`
- Create: `tests/test_market_browser_evidence.py`
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Add host-facing browser evidence CLI**

Create `scripts/browser_evidence.py` with commands:

```bash
python3 scripts/browser_evidence.py issue --context runs/raw/market/context.json --mode browser-cockpit-preflight
python3 scripts/browser_evidence.py approve-downgrade --context runs/raw/market/context.json --reason "Browser-native cockpit access was blocked; the user approved a one-off downgrade for this run."
```

Both commands must run through the runtime broker in product mode. The script must fail with `ok=false` if:

- active buddy is not Market;
- context does not contain the current run envelope;
- broker is unavailable;
- browser preflight is requested but the instance browser endpoint is unreachable;
- approved downgrade reason is empty.

Successful output shape:

```json
{
  "ok": true,
  "tool_evidence": {
    "browser_cockpit_token": "<broker-issued-browser-cockpit-token-for-current-run>"
  }
}
```

Approved downgrade output shape:

```json
{
  "ok": true,
  "tool_evidence": {
    "approved_downgrade_token": "<broker-issued-approved-downgrade-token-for-current-run>"
  }
}
```

- [ ] **Step 2: Extend broker protocol**

Add broker method `issue_browser_evidence` with payload:

```json
{
  "context": {},
  "mode": "browser-cockpit-preflight",
  "reason": null
}
```

Broker checks:

- profile has `tool_capability.browser_cockpit == "required"`;
- profile has `tool_capability.market_research_evidence == "required"`;
- context active buddy, instance id, task id, track id, context revision, and run id match current run envelope;
- browser endpoint from instance JSON `browser_port` responds to `/json/version` for preflight mode;
- approved downgrade mode has non-empty reason.

Broker writes token records under:

```text
$BUDDYSWITCH_INSTANCE_ROOT/runtime/evidence-tokens/run-<run-id>/<broker-issued-evidence-token>.json
```

Host writable roots must not include `$BUDDYSWITCH_INSTANCE_ROOT/runtime`.

- [ ] **Step 3: Validate Market persist evidence**

Extend persist validation for profiles with `market_research_evidence == "required"`:

- Market commit with one or more artifacts must include `tool_evidence.browser_cockpit_token` or `tool_evidence.approved_downgrade_token`.
- The token must exist in broker evidence token storage for the same instance id, buddy id, context revision, and run id.
- Missing token rejects persist before writes.
- Wrong run token rejects persist before writes.
- Approved downgrade token persists downgrade details into run audit under `tool_evidence`.
- Browser token persists evidence details into run audit under `tool_evidence`.

Do not accept a raw hand-written downgrade object as proof. The explicit downgrade record must be broker-issued so the rejection/approval path is observable.

- [ ] **Step 4: Adjust browser launcher behavior by profile**

Modify `tools/launcher/browser_cockpit.sh`:

- Market profile `browser_cockpit=required`: browser bootstrap failure aborts launch/open.
- PM/Design/Dev/Test `browser_cockpit=available`: attempt bootstrap, but if Chrome is unavailable or endpoint cannot start, continue launch/open with a clear warning and without evidence-required mode.
- `chrome-devtools-cockpit` MCP remains registered when the browser is available.

Keep existing `env browser ensure` command behavior strict when called directly.

- [ ] **Step 5: Add Market evidence tests**

Create `tests/test_market_browser_evidence.py`:

- Market profile requires browser evidence.
- Market persist with artifact and no evidence is rejected before writes.
- Market persist with broker-issued browser preflight token succeeds and run audit records token metadata.
- Market persist with broker-issued approved downgrade token succeeds and run audit records downgrade reason.
- Market persist with token for another run is rejected before writes.
- PM persist does not require `tool_evidence`.
- A hand-written `tool_evidence` token that has no broker record is rejected.

Run:

```bash
python3 -m unittest tests.test_market_browser_evidence -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

Expected: Market evidence is enforced by runtime tool feedback, not by AGENTS wording.

### Task 8: Integrate Product Launch/Open End-To-End

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/runtime_broker.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update start bootstrap order**

For `instance start --buddy market`, `instance start --buddy pm`, `instance start --buddy design`, `instance start --buddy dev`, and `instance start --buddy test`, enforce this order:

1. validate manifest buddy;
2. validate env profile;
3. bind instance env paths;
4. prepare execution workspace;
5. ensure project worktree;
6. repair live `projects/app` projection;
7. activate instance record;
8. validate/install runtime AGENTS;
9. install active buddy skills only;
10. patch Codex config from profile;
11. start runtime broker;
12. bootstrap browser according to profile;
13. set instance active;
14. launch Codex from instance workspace.

Any failure before step 7 must leave no instance record. Any failure after step 7 must set instance status to `inactive` or leave a clear failure record.

- [ ] **Step 2: Update open bootstrap order**

For `instance open inst-pm-example`, enforce this order for the buddy stored in the instance record:

1. validate instance id;
2. load instance record;
3. validate manifest buddy;
4. validate env profile;
5. validate execution workspace;
6. reject if instance is already active;
7. validate/install runtime AGENTS;
8. install active buddy skills only;
9. patch Codex config from profile;
10. start runtime broker;
11. bootstrap browser according to profile;
12. set instance active;
13. launch Codex from instance workspace.

- [ ] **Step 3: Add write probe tests**

Extend `tests/test_buddyswitch_launcher.py` fake Codex capture to inspect generated config roots and simulate product write probes using the profile matrix.

Required assertions:

- PM launch config excludes project workspace; Dev launch config includes project workspace.
- Runtime `projects/app` projection resolves to shared project source for all buddies.
- Test buddy config does not grant source write roots.
- State projection paths are not in writable roots.
- Broker socket env var is present for active buddy Codex sessions.
- Broker socket env var is absent for non-instance development sessions.

Use real Codex sandbox write probes as a manual verification command in Task 10 because the fake Codex test does not enforce Codex sandbox denials.

Run:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
```

Expected: product launcher emits profile-derived runtime shape for start/open.

### Task 9: Update Contracts And Durable Docs

**Files:**

- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/test.md`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update buddy contracts**

Update each contract with:

- project source access level;
- scratch root;
- raw state broker-only rule;
- active skills only;
- rejected tool action handling.

Add buddy-specific state authority:

- PM owns track lifecycle through `state_effects.track`.
- Market/Design/Dev/Test cannot mutate track lifecycle.
- Dev owns source writes.
- Test can run checks and write reports, but cannot edit source/tests/fixtures/snapshots/generated source.
- Market requires browser evidence or broker-issued approved downgrade.

- [ ] **Step 2: Update runtime docs**

Update `framework/docs/turn-runtime-spec.md`:

- `prepare`/`persist` product mode route through runtime broker;
- direct function calls are test/debug internals, not the product path;
- state writes are broker-owned;
- `tool_evidence` is optional generally and required by Market profile for artifact-producing commits.

Update `framework/docs/browser-cockpit.md`:

- Market browser cockpit is required;
- non-Market browser cockpit is available but not required;
- first evidence proof is broker-issued preflight token;
- approved downgrade must be broker-issued and recorded.

Update `framework/docs/architecture-overview.md`:

- env profile is capability source;
- AGENTS is context projection only;
- launcher compiles filesystem/tool capability;
- runtime broker enforces state capability.

- [ ] **Step 3: Add repo consistency checks**

Update `tests/test_repo_consistency.py` to assert:

- `framework/contracts/buddy-env-profile.json` is mentioned in runtime docs;
- `buddyswitch/env-profiles` is mentioned in architecture docs;
- docs do not say AGENTS is the permission source;
- docs do not describe raw host state writes as product behavior;
- no tracked runtime AGENTS template omits broker-only state wording.

Run:

```bash
python3 -m unittest tests.test_repo_consistency -v
```

Expected: docs describe the executed boundary and do not preserve prompt-only permission claims.

### Task 10: Final Verification And Manual Sandbox Probes

**Files:**

- No source edits unless verification exposes a defect.

- [ ] **Step 1: Run focused automated suites**

Run:

```bash
python3 -m unittest \
  tests.test_buddy_env_profiles \
  tests.test_buddy_env_sandbox \
  tests.test_runtime_broker \
  tests.test_market_browser_evidence \
  tests.test_turn_runtime \
  tests.test_turn_integration \
  tests.test_buddyswitch_launcher \
  tests.test_browser_cockpit_launcher \
  tests.test_repo_consistency \
  -v
```

Expected: all listed tests pass.

- [ ] **Step 2: Run full automated suite**

Run:

```bash
python3 -m unittest discover tests -v
```

Expected: full suite passes.

- [ ] **Step 3: Run real product sandbox write probes**

Use a disposable shared root:

```bash
export BUDDYSWITCH_SHARED_ROOT="$(mktemp -d)/.codex-buddyswitch"
./buddyswitch-codex instance start --buddy pm -- exec 'python3 - <<PY
from pathlib import Path
targets = [
    Path("projects/app/non-dev-write-probe.txt"),
    Path("buddyswitch/objects/tasks/non-dev-state-probe.json"),
]
for target in targets:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("probe\\n", encoding="utf-8")
        print(f"UNEXPECTED_WRITE:{target}")
    except Exception as exc:
        print(f"DENIED:{target}:{type(exc).__name__}")
PY'
```

Expected:

- PM probe prints `DENIED` for `projects/app/non-dev-write-probe.txt`.
- PM probe prints `DENIED` for raw state.
- No `UNEXPECTED_WRITE` lines appear.

Run Dev probe:

```bash
./buddyswitch-codex instance start --buddy dev -- exec 'python3 - <<PY
from pathlib import Path
source = Path("projects/app/dev-write-probe.txt")
source.write_text("dev-ok\\n", encoding="utf-8")
print(source.read_text(encoding="utf-8").strip())
state = Path("buddyswitch/objects/tasks/dev-state-probe.json")
try:
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{}\\n", encoding="utf-8")
    print("UNEXPECTED_STATE_WRITE")
except Exception as exc:
    print(f"STATE_DENIED:{type(exc).__name__}")
PY'
```

Expected:

- Dev probe prints `dev-ok`.
- Dev probe prints `STATE_DENIED`.
- No `UNEXPECTED_STATE_WRITE` line appears.

- [ ] **Step 4: Run real product prepare/persist broker probe**

Within a disposable PM instance, run:

```bash
python3 scripts/turn_runtime.py prepare "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track" > runs/raw/pm/context.json
python3 scripts/turn_runtime.py persist --context runs/raw/pm/context.json --result runs/raw/pm/result.json
```

Use a result JSON with `execution_summary`, PM `prd` artifact, `state_effects.track.create`, `state_effects.task`, and handoff to `market`.

Expected:

- prepare returns `ok=true`;
- persist returns `ok=true`;
- broker writes run audit under projected state;
- host raw state root is not writable according to sandbox config.

- [ ] **Step 5: Run Market evidence probe**

Within a disposable Market instance:

```bash
python3 scripts/turn_runtime.py prepare "调研 AI 日程工具 landing page 竞品表达" > runs/raw/market/context.json
python3 scripts/browser_evidence.py issue --context runs/raw/market/context.json --mode browser-cockpit-preflight > runs/raw/market/evidence.json
python3 scripts/turn_runtime.py persist --context runs/raw/market/context.json --result runs/raw/market/market-result-with-evidence.json
```

Expected:

- evidence issue returns `ok=true` with `browser_cockpit_token`;
- persist with token returns `ok=true`;
- the run audit includes `tool_evidence`.

Run a missing evidence persist against a fresh Market context.

Expected:

- persist returns `ok=false`;
- no artifact, task mutation, run audit, or reservation clear occurs.

- [ ] **Step 6: Inspect diff for scope**

Run:

```bash
git status --short
git diff --stat
git diff -- docs/spec/2026-05-06-buddy-instance-env-tool-layer-design.md
```

Expected:

- implementation files and tests match this plan;
- the original design spec is unchanged unless a deliberate review update is made;
- no repo-root `.agents` or runtime state artifacts are tracked.

## Review Rubric Before Claiming Completion

- Root cause: profile-derived environment and broker-controlled state replace prompt-only boundaries.
- Boundaries: launcher assembles environment; `scripts/**` owns host runtime tools and broker internals.
- No special-case drift: buddy differences come from profiles and manifest, not scattered if/else branches beyond launcher bootstrapping.
- Replacement: product-mode direct state writes are removed, not hidden behind fallback branches.
- Verification: automated tests plus real sandbox probes prove filesystem, state, and Market evidence behavior.
- Scope: no generic permission DSL, workflow engine, browser trace system, or command permission system is introduced.

## Compression Checkpoint (2026-05-07)

Current bottleneck:
- Live projection is restored, but non-dev runtime sessions can still write through projected `projects/app` and projected state paths in real product-mode probes, which violates FR5/FR7.

Confirmed evidence:
- Projection behavior was reverted to live-symlink semantics and targeted launcher tests pass.
- Focused suite (`191` tests) passed after cleanup of stale probe processes.
- Real PM product-mode probe still showed boundary leakage:
  - `UNEXPECTED_WRITE:projects/app/pm-probe.txt`
  - `UNEXPECTED_WRITE:buddyswitch/objects/tasks/pm-probe.json`
- Persist then failed with `E_RUNTIME_BROKER` after state-file corruption, proving this leak can break broker correctness.

Scope status:
- Work remains isolated to worktree `dev0210`.
- Projection fix stayed SHARP-minimal: direct symlink restore, no extra abstraction layers.

Next execution step:
- Fix root cause of non-dev write leakage with live projections (sandbox writable-root boundary vs symlink target resolution behavior), then rerun TG-08 probes, focused suite, full suite, and final review acceptance.
