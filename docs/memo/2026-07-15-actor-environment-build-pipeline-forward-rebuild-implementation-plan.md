# Actor Environment Build Pipeline Forward Rebuild Implementation Plan

> **For agentic workers:** execute this plan inline, task by task, using test-first changes and the repository's `./buddyswitch-test focused` entry. Do not run `./buddyswitch-test full` unless the candidate is explicitly frozen for repository-wide acceptance. Do not introduce migration, fallback, compatibility wrappers, or parallel worktree/copy paths.

**Goal:** Replace the scattered actor worktree/sparse/sync build path with one `ActorEnvironmentBuilder` that allowlist-copies a Git-free shared project environment and actor environment through staging, validates the final shape, and atomically publishes it before HostControl starts runtime services.

**Architecture:** CLI and Web remain peer adapters that converge on `HostControl.start`; neither imports or calls the builder. Under the lifecycle lock, `host_control.sh` constructs one explicit builder request, invokes `tools/launcher/actor_environment.py` exactly once, and starts broker/app/daemon services only after a successful typed build result. The builder owns filesystem materialization and shape proof; HostControl retains actor IDs, records, capabilities, runtime processes, failure mapping, resume/stop/delete, and external results.

**Tech stack:** Python 3.13 dataclasses/pathlib/shutil/os, Bash HostControl integration, existing `scripts/runtime_skills.py`, unittest/pytest, BuddySwitch focused test runner.

---

## Target outcome and non-negotiable invariants

1. `tools/launcher/actor_environment.py` is the only actor environment build owner.
2. The fixed build order is preflight -> seed shared project once -> actor staging -> roots -> runtime copy -> role surface -> projections -> final validation -> atomic publish.
3. Source material is copied only through code-owned allowlists. No build step invokes Git or copies, creates, repairs, removes, or interprets `.git`.
4. `${shared_root}/project/workspace` is seeded from source `projects/app` only when absent. Once present, it is validated but never overwritten, refreshed, merged, or source-synced.
5. `${shared_root}/instances/<actor-id>` is absent until the fully validated staging tree is renamed into place. Any actor build failure removes its staging tree and leaves the formal actor root absent.
6. The formal project and actor outputs contain no `.git` entry at any depth. The only required actor-workspace projection symlink is `workspace/projects/app` to the stable shared project `projects/app`; `workspace/private` is a real writable directory.
7. CLI and Web continue to call `HostControl`; build behavior does not become a new public command, HTTP route, workflow engine, or launcher-wide refactor.
8. Existing worktree/sparse/HEAD-sync/repair/guardrail-hook actor build code, actor-specific tests, fixtures, cleanup registrations, names, and live documentation are deleted rather than wrapped.
9. Existing actor environments that do not satisfy the current Git-free shape fail closed on resume; they are not migrated or repaired.
10. Only `./buddyswitch-test focused <explicit-target>...` is used for RED/GREEN/IMPACT during implementation.

## Current state and scope partition

- HEAD at plan creation: `625aa5d` (`Merge branch 'fea-daemon'`).
- Pre-existing non-ignored untracked file: `docs/memo/2026-07-15-actor-environment-build-pipeline-forward-rebuild-review.html` (the approved design input; preserve it).
- No tracked implementation changes existed when this plan was created.
- Current shared external path is already correct: CLI and Web call `HostControl.start`.
- Current bottleneck is below HostControl: `host_control.sh` sources `workspace.sh` and sequences execution worktree, project worktree, projection repair, private creation, skill installation, Git synchronization, and service startup.
- Generic test-runner Git-worktree coordination for developer checkouts is outside scope. Remove actor-environment registrations from the system fixture, but retain generic runner support that is independently used to coordinate test worktrees.

## File responsibility map

**Create**

- `tools/launcher/actor_environment.py` — specs/results, fixed allowlist, preflight, copy, customization, validation, staging cleanup, atomic publish, internal JSON process boundary.
- `tests/unit/launcher/test_actor_environment.py` — exact builder behavior, negative shape, seed-once, and failure atomicity.
- `tests/system/instance_lifecycle/test_environment_build_safety.py` — real CLI lifecycle proof for Git-free shape, preserved project content, reset, and unsafe-root rejection.

**Modify**

- `scripts/runtime_skills.py` — expose a read-only preflight validation function backed by the existing install plan; keep `install_runtime_skills()` as the sole materializer.
- `tools/launcher/host_control.sh` — replace all actor build calls with one builder invocation; remove workspace helper sourcing; validate current env on resume; use owned filesystem removal on delete.
- `tools/launcher/env.sh` — own environment bindings and generic safe path/removal helpers only; stop sourcing or depending on `workspace.sh`; set the fixed shared project path.
- `tools/launcher/cli.py` — reset removes the owned shared filesystem directly and no longer sources or invokes worktree cleanup.
- `tests/process/launcher/test_instance_commands.py` — replace worktree-registration delete expectations with owned-directory deletion and Git-free safety expectations.
- `tests/process/cli/test_host_control.py` — assert the private HostControl architecture has one builder path and no workspace/worktree build dependency.
- `tests/system/instance_lifecycle/test_main_flow.py` — assert real runtime/project/private paths are Git-free and shared project survives actor deletion.
- `tests/system/instance_lifecycle/runner_instance_start_fixture.py` — stop registering actor/project worktrees for cleanup; register only owned filesystem/process resources already managed by the harness.
- `tests/process/launcher/test_public_cli.py` — remove the retired locked-workspace terminology test if it no longer represents a live contract; retain only generic unknown-command coverage.
- `tests/unit/architecture/test_external_control.py` and/or `tests/unit/architecture/test_repo_contracts.py` — lock CLI/Web -> HostControl and HostControl -> sole builder ownership; forbid production references to the deleted helper.
- `README.md`, `AGENTS.md`, and current architecture/runbook text found by residue search — describe only copy-built Git-free environments where actor build semantics are mentioned.

**Delete**

- `tools/launcher/workspace.sh`.
- `tests/system/instance_lifecycle/test_worktree_safety.py` after equivalent current-contract proof exists in `test_environment_build_safety.py`.
- Actor-specific worktree cleanup assertions/fixtures and production/test strings that describe execution worktrees, project worktrees, sparse checkout, HEAD sync, repair, or guardrail hooks as current product behavior.

## Concrete builder contract

```python
@dataclass(frozen=True)
class ActorEnvironmentSpec:
    repo_root: Path
    shared_root: Path
    actor_id: str
    role_id: str
    source_codex_home: Path


@dataclass(frozen=True)
class ActorEnvironmentResult:
    actor_root: Path
    workspace_dir: Path
    project_workspace_dir: Path
    private_dir: Path
    home_dir: Path
    codex_home_dir: Path
    xdg_config_home: Path
    tmp_dir: Path
    installed_skills: tuple[str, ...]


class ActorEnvironmentBuilder:
    def build(self, spec: ActorEnvironmentSpec) -> ActorEnvironmentResult:
        """Materialize, validate, and atomically publish one actor environment."""
```

The module's internal process adapter accepts the five spec fields, calls `ActorEnvironmentBuilder().build(spec)` once, and writes one JSON result. It is invoked only by private HostControl; it is not registered in the public CLI.

`RUNTIME_COPY_PATHS` starts from the current live runtime boundary and remains explicit:

```python
RUNTIME_COPY_PATHS = (
    "scripts/env",
    "scripts/runtime_kernel",
    "scripts/turn_runtime.py",
    "scripts/env_store.py",
    "scripts/env_legacy_store.py",
    "scripts/env_manifest.py",
    "scripts/env_profiles.py",
    "scripts/browser_evidence.py",
    "buddyswitch/manifest.toml",
    "buddyswitch/env-profiles",
    "framework/contracts",
)
```

Copy helpers skip every path component named `.git`; final validation independently rejects any `.git` entry so a copy bug cannot publish a Git-bearing output.

## Task 1: Define exact builder behavior with RED tests

**Files:**

- Create: `tests/unit/launcher/test_actor_environment.py`

- [x] Add a temporary-repository fixture containing the exact runtime allowlist, `projects/app`, one role AGENTS file, a minimal manifest, one skill directory, and source Codex auth.
- [x] Add `test_build_materializes_typed_git_free_actor_environment` asserting every result path, copied runtime path, installed role AGENTS/skill, base config/auth surface, writable real private directory, exact project symlink target, and absence of `.git` anywhere in actor/project outputs.
- [x] Add `test_build_seeds_shared_project_once_without_refresh` that changes both source and shared project after the first build, builds a second actor, and proves the shared sentinel/content remains unchanged and new source content is not synchronized.
- [x] Add `test_preflight_failure_writes_nothing` covering missing allowlisted source, missing/invalid role asset, unsafe symlink root, invalid actor/role IDs, and an existing actor target. Assert no project staging, actor staging, or formal target remains.
- [x] Add `test_invalid_existing_shared_project_is_rejected_without_overwrite` for a missing `projects/app`, symlinked root, or `.git` residue; assert the existing content is untouched.
- [x] Add `test_actor_copy_failure_cleans_staging_and_does_not_publish` by injecting a deterministic copy failure after project seed is already valid.
- [x] Add `test_actor_validation_failure_cleans_staging_and_does_not_publish` by injecting forbidden `.git` immediately before final validation.
- [x] Add `test_actor_publish_failure_cleans_staging_and_does_not_publish` by injecting a deterministic actor `os.replace` failure while an already-valid shared project avoids ambiguity with project publish.
- [x] Add `test_project_seed_failure_cleans_project_staging` and prove the formal project root remains absent.
- [x] Add `test_runtime_copy_allowlist_excludes_repo_surfaces` asserting `tools`, `tests`, `docs`, `README.md`, launcher scripts, and source `.git` do not appear in the actor workspace.

Run RED:

```bash
./buddyswitch-test focused tests/unit/launcher/test_actor_environment.py
```

Expected: collection/import failure because `tools.launcher.actor_environment` does not exist. This is valid RED only after the test module itself imports cleanly apart from the missing production module.

Record RED evidence with HEAD, tracked patch identity, both untracked plan/review files, command, environment, exit/result, cleanup state, and exact missing-owner claim.

## Task 2: Implement the fixed builder SOP to GREEN

**Files:**

- Create: `tools/launcher/actor_environment.py`
- Modify: `scripts/runtime_skills.py`

- [x] Expose `validate_runtime_skills(manifest_path, role_id) -> tuple[str, ...]` as a read-only view of the same `_build_install_plan()` used by `install_runtime_skills()`; do not create another skill-copy loop.
- [x] Implement immutable spec/result dataclasses and one `ActorEnvironmentBuildError` with actionable messages.
- [x] Normalize and confine `shared_root`, project root, actor root, staging parents, and source paths. Reject symlinked roots and an existing actor root before mutation.
- [x] Validate every allowlisted runtime source, source project directory, role AGENTS, manifest role/skill plan, and source auth input before creating staging.
- [x] Seed `${shared_root}/project/workspace` through a sibling staging directory and `os.replace` only when absent; otherwise validate current shape without writing it.
- [x] Create one sibling actor staging root under `${shared_root}/instances`, materialize workspace/home/codex-home/xdg-config/tmp/private, install base config/auth, copy the runtime allowlist, copy role AGENTS, and call `install_runtime_skills()` once.
- [x] Create `workspace/projects/app` as the exact shared-project projection and keep `workspace/private` as a real directory.
- [x] Validate required paths, forbidden repo surfaces, projection target, private writability, root confinement, and recursive `.git` absence against staging plus the stable project root.
- [x] Atomically publish staging to the formal actor root and construct the result from published paths.
- [x] Clean only owned staging paths on every exception; never recursively replace an existing formal target.
- [x] Add the private JSON process adapter without registering a public command.
- [x] Re-run the exact Task 1 command until GREEN.
- [x] Run the directly affected runtime-skill contract:

```bash
./buddyswitch-test focused tests/unit/actor/test_runtime_skills.py
```

Expected: both focused commands pass with no staging residue under their temporary shared roots.

## Task 3: Integrate the sole builder below HostControl

**Files:**

- Modify: `tools/launcher/host_control.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/process/cli/test_host_control.py`
- Modify: `tests/process/launcher/test_instance_commands.py`

- [x] First add process/architecture assertions that `start_locked_bootstrap` invokes `actor_environment.py` once, that `workspace.sh` and `buddyswitch_workspace_*` are absent from the private HostControl path, and that broker/app/daemon calls occur after the build result.
- [x] Add a start-failure process case with a deterministic builder preflight failure and assert no instance record or runtime process start occurs.
- [x] Run those exact new node IDs and observe RED against the current scattered calls.
- [x] Remove `workspace.sh` sourcing from `host_control.sh` and `env.sh`.
- [x] Make `buddyswitch_env_init` bind the fixed `${shared_root}/project/workspace` path and retain only environment/runtime configuration facts.
- [x] Move the two generic, non-build filesystem operations still needed by delete/reset (canonical-path confinement and owned recursive removal) into `env.sh` with names that do not preserve workspace build ownership.
- [x] Replace the start block from shared/worktree preparation through projection/private setup with one captured builder JSON invocation. Continue to instance record/capabilities/broker/config/browser/app/thread/daemon only on builder success.
- [x] Make resume validate the current Git-free required shape without seed, refresh, repair, or build fallback; invalid legacy shape returns lifecycle-blocked guidance to delete/reset and recreate.
- [x] Make delete remove the already-confined actor directory directly without Git worktree deregistration.
- [x] Keep `buddyswitch_patch_codex_config`, environment MCP, browser, app-server, broker, daemon, thread, and record ownership in their current modules. Actor runtime preparation now only patches runtime configuration and TTL state; it cannot create or repair build-owned config/auth/private surfaces.
- [x] Run the same RED node IDs to GREEN, then run direct HostControl/process impact:

```bash
./buddyswitch-test focused \
  tests/process/cli/test_host_control.py \
  tests/process/launcher/test_instance_commands.py
```

## Task 4: Replace reset, actor cleanup, and worktree fixtures

**Files:**

- Modify: `tools/launcher/cli.py`
- Modify: `tests/system/instance_lifecycle/runner_instance_start_fixture.py`
- Modify: `tests/support/processes.py` only if a product-specific branch remains after registrations are removed
- Modify: `tests/process/launcher/test_public_cli.py`

- [x] Rewrite reset expectations first: an inactive Git-free environment is removed by owned filesystem deletion, an active instance still blocks reset, unsafe roots still fail closed, and no Git command is part of the reset owner script.
- [x] Observe RED on the exact changed reset tests.
- [x] Remove `workspace.sh` from `_source_helpers_script()` and replace reset's registered-worktree cleanup plus force removal with the generic owned-root removal helper.
- [x] Remove actor/project `git_worktree_remove` registrations from `runner_instance_start_fixture.py`; retain process cleanup and owned shared-root cleanup.
- [x] Remove only product-specific cleanup strategy code that has no remaining independent runner use. Generic developer/test-runner worktree coordination remains independently covered in `tests/integration/support/test_run_supervisor.py`.
- [x] Delete the locked-workspace-sync dedicated test if it exists only to preserve retired terminology; generic unknown-command tests continue to prove no hidden public command exists.
- [x] Run focused process proof:

```bash
./buddyswitch-test focused \
  tests/process/launcher/test_public_cli.py \
  tests/integration/support/test_run_supervisor.py
```

The integration support target is required only if `tests/support/processes.py` changes; otherwise omit it and record that discovery stopped before unrelated runner infrastructure.

## Task 5: Replace worktree system safety with current environment safety

**Files:**

- Delete: `tests/system/instance_lifecycle/test_worktree_safety.py`
- Create: `tests/system/instance_lifecycle/test_environment_build_safety.py`
- Modify: `tests/system/instance_lifecycle/test_main_flow.py`

- [x] Write system cases proving a real `instance start` produces the allowlisted Git-free actor/project shape and does not register either path in `git worktree list`.
- [x] Prove the shared project is seeded once: add a sentinel after actor A, start actor B, and assert the sentinel survives and both actors project to the same shared directory.
- [x] Prove actor deletion removes only its actor root and leaves the shared project/other actor state untouched across the system main flow and process delete contract.
- [x] Prove `env reset --yes` removes the owned shared root after instances stop without any worktree cleanup behavior.
- [x] Prove unsafe/symlinked shared or instance roots fail closed without touching external sentinel content through exact builder and process delete tests.
- [x] Prove `test_main_flow` still observes CLI start -> input -> status -> stop -> resume -> delete, runtime cwd/private/project bindings, and no `.git` in published environment roots.
- [x] Run the new system target separately because the runner may declare it exclusive:

```bash
./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
```

## Task 6: Lock architecture and remove the old owner

**Files:**

- Delete: `tools/launcher/workspace.sh`
- Modify: `tests/unit/architecture/test_external_control.py`
- Modify: `tests/unit/architecture/test_repo_contracts.py` if that is the direct current owner
- Modify: current docs identified by live residue search

- [x] Add architecture assertions before deletion: CLI and Web import/call HostControl, neither references `ActorEnvironmentBuilder`, `host_control.sh` has exactly one builder invocation, and no production file sources `workspace.sh`.
- [x] Add a repository residue assertion that the deleted actor build symbols/phrases are absent from live production and actor-lifecycle tests while excluding the approved review/implementation memo and generic test-runner worktree coordination.
- [x] Observe RED, delete `workspace.sh`, and remove all now-dead calls/tests/fixtures.
- [x] Search live product paths:

```bash
rg -n "workspace\.sh|buddyswitch_workspace_|execution worktree|project worktree|sparse-checkout|sparse checkout|force_rebuild_.*worktree|repair_runtime_projects_app|sync_runtime_surface|install_guardrail_hooks" \
  tools scripts tests README.md AGENTS.md docs/arch
```

Expected: no actor-environment production or current-contract residue. Any remaining match must be either a generic developer test-runner worktree contract or an explicit negative assertion; classify it in the evidence record.

- [x] Search for Git behavior in the new owner and its HostControl call path:

```bash
rg -n "subprocess|git |\.git|worktree|sparse|checkout|HEAD|sync|repair|fallback|migration|compat" \
  tools/launcher/actor_environment.py tools/launcher/host_control.sh tools/launcher/env.sh
```

Expected: `.git` appears only in explicit reject/skip validation; no Git command, legacy path, or fallback branch exists.

- [x] Run architecture proof:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_external_control.py \
  tests/unit/architecture/test_repo_contracts.py
```

## Task 7: Claim-scoped IMPACT verification and completion audit

- [x] Re-read `.agents/skills/buddyswitch-testing/references/escalation.md` before deciding final breadth.
- [x] Inspect `git status --short`, rename-aware diff, non-ignored untracked files, and live references. Partition the approved review memo from implementation changes but include it in source identity.
- [x] Reuse unchanged GREEN evidence only where source, command, environment, result, and claim remain equivalent.
- [x] Run compatible focused IMPACT batches for the exact builder, HostControl/process, architecture, runtime-skills, browser handoff, and main lifecycle targets that remain direct after the final diff. Keep runner-declared system targets separate.
- [x] Do not run `./buddyswitch-test full` for ordinary local completion. It was intentionally not run because this is not a frozen repository-wide acceptance request.
- [x] Audit every target invariant at the top of this plan against current files, focused outputs, filesystem observations, and residue searches. Missing or indirect evidence is incomplete, not success.
- [x] Update the progress and evidence sections below with exact commands, identities, cleanup state, and residual risk.

## Progress

- [x] Required repository guidance, review memo, testing skill, and external HostControl boundary read.
- [x] Current worktree, source owners, existing tests, and legacy build functions mapped.
- [x] Resumable implementation plan created before production/test implementation.
- [x] Builder RED recorded.
- [x] Builder GREEN recorded.
- [x] HostControl integration GREEN/IMPACT recorded.
- [x] Reset/delete/system cutover recorded.
- [x] Legacy owner/residue deletion recorded.
- [x] Completion audit passed.

## Verification evidence

This plan was created before executable implementation. The evidence records below were appended after each meaningful block:

```text
Verification Evidence
- state: <RED | GREEN | IMPACT | MILESTONE>
- source: repo=/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD=<sha>; tracked-patch=<identity>; untracked=<identity>
- command: ./buddyswitch-test focused <explicit targets>
- environment: <runner/toolchain/material environment>
- result: <exit status, summary, duration, cleanup/residual state>
- proves: <exact behavior and direct boundaries>
- valid-for: <current worktree identity>
- residual-risk: <none or explicit boundary>
```

### RED — sole builder and exact behavior contract

```text
Verification Evidence
- state: RED
- source: repo=/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf; tracked-patch=sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855; untracked=implementation-plan:4187599234541edcc70347b8232fec96851676643a9a32195d2bfecb578c581d,review:762d8dfa7d6b5601d1a302487cdfe3f03eae21d7000dc4921d58979a550b917d,builder-tests:f4b8cafc666afda62dadd36ea19394e1580aff6c2f2385ec7a8b29697f486473
- command: ./buddyswitch-test focused tests/unit/launcher/test_actor_environment.py
- environment: BuddySwitch focused-python runner; /Users/chen/miniconda3/bin/python; pytest; run id f974593f7ffd402482c76f264d4b71b9
- result: exit 1; 10 assertion failures in 0.08s because tools.launcher.actor_environment is absent; focused runner failed in 0.23s; no setup/import/environment failure; run root cleanup reported no residue
- proves: the exact builder contract detects the missing single ActorEnvironmentBuilder owner before production implementation
- valid-for: recorded RED source identity only
- residual-risk: later runs must expose behavior-specific failures if the module exists but behavior is incomplete
```

### GREEN — builder SOP and runtime skill boundary

```text
Verification Evidence
- state: GREEN
- source: repo=/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf; tracked-patch=sha256:3975695187a11f5739d9bded6ce342b39c5b3930266e6b3af5e771cd9c8deca6; untracked=implementation-plan:da61485f5b3ab663acfd9418fbf39970f7469e575e94f1b56c2b6a674e55b12a,review:762d8dfa7d6b5601d1a302487cdfe3f03eae21d7000dc4921d58979a550b917d,builder-tests:f4b8cafc666afda62dadd36ea19394e1580aff6c2f2385ec7a8b29697f486473,builder:b9b4cf9b984fc7cc52a8acca626955e40da9c86b32297f66d9d910eabfd5a62c
- command: ./buddyswitch-test focused tests/unit/launcher/test_actor_environment.py
- environment: BuddySwitch focused-python runner; /Users/chen/miniconda3/bin/python; pytest; run id 3cf9e8418dd24ebfb909512a35c1b29a
- result: exit 0; 10 passed and 4 subtests passed in 0.15s; focused runner passed in 0.27s; no cleanup residue reported
- proves: fixed allowlisted builder SOP, typed paths, Git-free outputs, project seed-once, preflight safety, staging cleanup, and atomic actor/project failure behavior
- valid-for: recorded GREEN source identity
- residual-risk: HostControl is not yet routed through the builder
```

```text
Verification Evidence
- state: IMPACT
- source: same source identity as builder GREEN
- command: ./buddyswitch-test focused tests/unit/actor/test_runtime_skills.py
- environment: BuddySwitch focused-python runner; /Users/chen/miniconda3/bin/python; pytest; run id 1aded5b89b734eeaaf049ddb22d391ab
- result: exit 0; 36 passed and 291 subtests passed in 0.14s; focused runner passed in 0.24s; no cleanup residue reported
- proves: read-only skill-plan validation and Git-filtered installation preserve the existing runtime skill contract
- valid-for: recorded GREEN source identity
- residual-risk: none within the runtime-skill owner
```

### FINAL GREEN / IMPACT — current executable candidate

```text
Verification Evidence
- state: RED -> GREEN
- source: current executable line descended from HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf
- commands/results:
  - private writability: run 43f9f42a93ae45d8a58a145765725206 failed because read-only private was accepted; run 78a47b98bec342f5845f09206bc786f6 passed after owner-write validation
  - base config/auth: run ddcb027a4a204e0c97b242c2d27738fb failed in both subtests; run 3b1da8d8e2be43e994d3655109a86ae9 passed with 2 subtests after exact projection validation
  - sole env owner: run 3d4437e51f5a464196961bcb23e4d823 failed while env.sh retained a second private/config/auth materializer; run 311e90ea6fc14556b61f43dd0f353476 passed with 4 subtests after actor runtime preparation was reduced to runtime-only facts
  - nested/output symlink confinement: runs 6994a6969b89493da85f3b8f930dbec7 and 74202762808c4b478a78190b364288e9 failed on the intended missing checks; run 2a931239e0f746b78bc6e9876efb0d67 passed 2 tests and 8 subtests after preflight/final-shape enforcement
- environment: BuddySwitch focused-python runner; /Users/chen/miniconda3/bin/python; pytest
- cleanup: every listed focused run reported no cleanup residue
- proves: the exact regressions independently detect the missing shape/ownership/confinement behavior before the corresponding minimal implementation
- residual-risk: none within these exact contracts
```

```text
Verification Evidence
- state: GREEN / IMPACT
- source: repo=/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf; tracked-patch=sha256:81188bf27f652579519b97fed59784c808d428287ff27fcd59a10c8ff58eb0c6; untracked-review=762d8dfa7d6b5601d1a302487cdfe3f03eae21d7000dc4921d58979a550b917d; untracked-builder=508d667dba0e65040852e2968395ef644beeb4613c0339da4e63ab09ea3c8e18; untracked-builder-tests=986dbbe837b9f32ff2578a5c1288913148160773f3505a1e73b1bdcd1bff4c98; untracked-system-safety=223f9bcc7405fb45a31467a58ffe532d65fbe4f412f5a4159caa0c9b20f13acf; implementation plan excluded from its own self-referential hash
- command: ./buddyswitch-test focused tests/unit/launcher/test_actor_environment.py tests/unit/actor/test_runtime_skills.py
- result: run 168606d28ef348b4a5c77363884ee771; exit 0; 50 passed and 301 subtests passed in 0.42s; no cleanup residue reported
- proves: fixed builder SOP, allowlist, seed-once, typed result, base config/auth/private/project shape, zero-write preflight, nested path confinement, Git filtering plus independent rejection, staging cleanup, atomic failure paths, validate-only resume contract, and shared runtime-skill install planning
- valid-for: current builder/runtime-skill source identity
- residual-risk: none within the builder and runtime-skill owners
```

```text
Verification Evidence
- state: IMPACT
- source: same current executable candidate; browser/env/HostControl sources unchanged after this owner-scoped run
- command: ./buddyswitch-test focused tests/process/launcher/test_browser_cockpit.py tests/process/launcher/test_browser_commands.py tests/process/launcher/test_bootstrap_config.py tests/process/cli/test_host_control.py tests/process/launcher/test_instance_commands.py tests/unit/architecture/test_external_control.py
- result: run 893574e7b8c84bf49418bd59a223bee2; exit 0; 102 passed and 150 subtests passed in 39.46s; no cleanup residue reported
- proves: runtime-only actor preparation preserves browser/launcher behavior while CLI/Web remain outside the builder and HostControl keeps the sole start boundary
- valid-for: current browser/env/HostControl/architecture source identity
- residual-risk: none within the browser handoff and external-control boundary
```

```text
Verification Evidence
- state: IMPACT
- source: current executable candidate identity above
- command: ./buddyswitch-test focused tests/process/cli/test_clean_runtime_environment.py tests/process/launcher/test_instance_commands.py tests/process/cli/test_host_control.py tests/unit/architecture/test_external_control.py tests/unit/architecture/test_repo_contracts.py
- result: run c75aa80d72d7444c9c623f0661c788b6; exit 0; 69 passed and 143 subtests passed in 10.32s; no cleanup residue reported
- proves: current builder integrates below HostControl, deterministic build failure blocks record/runtime creation, clean runtime shape is Git-free, delete is owned-filesystem-only, and architecture/repository contracts reject the retired owner
- valid-for: current process/architecture source identity
- residual-risk: none within direct HostControl/process boundaries
```

```text
Verification Evidence
- state: MILESTONE
- source: current executable candidate identity above
- commands:
  - ./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
  - ./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
- result: runs dcc08c0f18f04333ac059c2fa652e005 and 2c8eeeb0943244949fee082bd1b795b4; exit 0; 4 passed in 13.33s and 1 passed in 5.67s; no cleanup residue reported
- proves: two actors share one preserved Git-free/non-worktree project env; reset removes the owned env; active/inactive resume rejects invalid shape without repair; start -> input -> status -> stop -> resume -> stop -> delete remains live with project/private/runtime bindings and shared project survival
- valid-for: current system lifecycle source identity
- residual-risk: Web transport was not separately driven end-to-end; its shared HostControl ownership is locked by architecture tests, and the filesystem/lifecycle owner itself is exercised through the public CLI
```

```text
Verification Evidence
- state: COMPLETION AUDIT
- source: current executable candidate identity above; implementation-plan edits are non-executable evidence updates
- checks: python -m py_compile tools/launcher/actor_environment.py scripts/runtime_skills.py; bash -n tools/launcher/env.sh tools/launcher/host_control.sh tools/launcher/browser_cockpit.sh; git diff --check; live rg residue scans
- result: all syntax/diff checks exited 0; production/current-doc scans found no actor worktree/sparse/sync/repair owner; new path contains no Git command and `.git` appears only in explicit copy exclusion/rejection; remaining worktree test references are negative assertions, Git-free registration probes, or independent test-runner/developer-worktree infrastructure
- proves: candidate is syntactically valid, whitespace-clean, and old actor build residue is absent from live ownership paths
- residual-risk: `./buddyswitch-test full` was intentionally not run because the user did not request FINAL repository-wide acceptance
```

## Key decisions

- The approved HTML review is the design authority; this plan does not reopen its architecture.
- The shared project path is fixed at `${shared_root}/project/workspace`; an environment override cannot create a second projection/build path.
- Actor staging publishes the entire instance root, not only `workspace`, so home/codex-home/xdg/tmp/private are covered by the same atomic boundary.
- Project seed and actor publish are separate atomic operations. A successful first project seed may remain if a later actor build fails; the actor formal root must still remain absent.
- `install_runtime_skills()` remains the only skill copier. Preflight exposes its existing plan as read-only validation.
- Generic repository/test-runner worktree support remains only where it serves developer checkout coordination independently of actor environments.

## Remaining risk at plan creation

- Resume currently re-runs shared/workspace preparation. The cutover must replace this with strict current-shape validation without accidentally refreshing project or runtime files.
- Browser registration calls `buddyswitch_ensure_shared_env`; that helper must not recreate actor build ownership or mutate shared project content after the builder publishes.
- Runtime skill sources are validated relative to the loaded checkout. Builder tests must patch that source root or use the live checkout so temporary manifests do not accidentally validate against a different repository.
- System lifecycle tests own real subprocesses and cleanup. Each focused run must report cleanup residue, and a failed/timeout run supersedes earlier passing evidence until diagnosed.
