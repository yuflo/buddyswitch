# S1 C2–C5 Atomic Installed-Runtime Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task by task. Follow root
> `AGENTS.md` and `$buddyswitch-testing`.

**Goal:** Move every current BuddySwitch implementation/resource into one
installed package, cut every public and child process to verified package
entrypoints, publish code-free Actor workspaces, and preserve the complete
lifecycle before returning for C6.

**Architecture:** The existing package activation owner remains the single
runtime-identity authority. The atomic replacement path is
`root interface -> verified package entrypoint -> current owner`; package
resources replace repository paths, and Actor build projects only selected
Role/Skill/config/private/project content. There is no compatibility or
intermediate deployed truth.

**Tech stack:** Python 3.13, `setuptools.build_meta`, non-editable wheel
installation, existing shell process orchestration as installed package data,
and the single `./buddyswitch-test` interface.

## 1. Stage identity

```text
Stage:
S1 / C2–C5

Charter:
../01-single-package-runtime-cutover.md

State:
READY

Source:
S1-C2-C5-SOURCE-SNAPSHOT.md

Scope:
S1-C2-C5-CONSUMER-MANIFEST.md

Preflight:
S1-C2-C5-PREFLIGHT.md

Stage executor:
one independent session

Migration/acceptance owner:
coordinating hub

Plan review date:
2026-07-28
```

## 2. Acceptance sentence

> Every current BuddySwitch capability in the C2–C5 candidate executes from
> one installed package built from `src/buddyswitch/**`; every BuddySwitch
> process reports the activated runtime identity; Actor workspaces contain
> only selected projections; all old executable/resource roots are absent;
> the complete current lifecycle remains behaviorally unchanged and clean.

Consumer path:

```text
public CLI / Web / IM / Daemon / Actor action
  -> verified installed package entrypoint
    -> current semantic owner using package resources and explicit locators
      -> one observable result, one runtime identity and exact cleanup
```

## 3. Protected contracts and direct-Forward boundary

Preserve exactly:

- public CLI command names, JSON result/error contracts and exit behavior;
- Role set, authority, bootstrap result and selected Skills;
- Tool IDs, actions, input schemas, permission rules and terminal results;
- start, list/status, input, interrupt, compact, clear, resume, stop and delete
  state effects;
- Web retry, IM delivery/worker, Daemon scheduling/recovery, App and Browser
  lifecycle behavior;
- shared `projects/app` seed-once/projection/delete semantics;
- cleanup, symlink, path-containment, PID, process-group, socket and lock
  safety;
- canonical persisted data paths and contents.

Direct Forward cutover:

- no internal Python import path is protected;
- no retired source path, process argument or workspace implementation layout
  is protected;
- no canonical data is moved or dual-written;
- new Actor starts record the exact activation record as
  `runtime_identity`;
- resume requires the recorded identity to equal current verified identity;
  missing or mismatched attribution fails before mutation. The frozen source
  snapshot contains no current Actor requiring data migration.

## 4. Frozen decisions

Apply D-002–D-009, D-020, D-022, D-025–D-030, D-033–D-038.

In particular:

- `src/buddyswitch/**` is the only implementation/runtime source root;
- `pyproject.toml` is the only build/content owner;
- every process uses one installed distribution;
- Actor workspaces contain no BuddySwitch implementation;
- root wrappers remain thin stable interfaces;
- tests remain root-owned and use the one public runner;
- C2–C5 is one atomic candidate; C6 alone owns current root/docs guidance,
  final residue classification and `full`.

## 5. Proof map

The executor first adds these exact cross-boundary assertions and observes
them fail against the current old topology:

| Claim | Test file / exact test |
|---|---|
| old runtime roots are gone and all target package owners/entrypoints exist | `tests/unit/architecture/test_package_contract.py::test_atomic_cutover_has_one_source_and_entrypoint_topology` |
| all moved resources, including four `LICENSE*`, ship and tests/cache do not | `tests/process/package/test_distribution_install.py::test_atomic_cutover_distribution_contains_every_required_runtime_resource` |
| public launchers use only activated package/runtime and fail closed | `tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_root_launcher_uses_only_verified_installed_package` |
| Broker launch is `sys.executable -m ...runtime_broker` with no repo-root/source loader | `tests/process/services/test_runtime_broker_lifecycle.py::test_broker_command_uses_only_installed_module_and_explicit_state_paths` |
| Actor output is exactly code-free and selected | `tests/unit/launcher/test_actor_environment.py::ActorEnvironmentBuilderTests::test_actor_workspace_contains_only_selected_projection` |
| a started Actor uses one installed identity and no copied implementation | `tests/system/instance_lifecycle/test_environment_build_safety.py::TestEnvironmentBuildSafety::test_started_actor_is_code_free_and_runtime_attributable` |

Expected RED causes only:

```text
old source roots still exist
root wrappers/source children still use checkout paths
launcher LICENSE resources do not yet ship
Actor still copies implementation
instance/process identity is not yet projected
```

An import error, unrelated behavior failure or different semantic expectation
is not an accepted RED.

## 6. Task sequence

### Task 1 — Verify source, partition and quiescence

- [ ] Read root `AGENTS.md`, `$buddyswitch-testing`,
  `S1-C2-C5-SOURCE-SNAPSHOT.md`, `S1-C2-C5-CONSUMER-MANIFEST.md`,
  `S1-C2-C5-PREFLIGHT.md`, this plan and the Goal Packet.
- [ ] Recompute HEAD, tracked/index hashes, twelve-path non-memo identity and
  the 228-path move partition.
- [ ] Record the complete coordinating `docs/memo/**` identity.
- [ ] Confirm no BuddySwitch process, Actor instance owned by this checkout,
  socket, PID or lock is active.
- [ ] Record the verified current activation identity.
- [ ] Update only `S1-C2-C5-EXECUTION-STATE.md`.

Stop on any disagreement. Do not normalize the source to match the packet.

### Task 2 — Establish cross-boundary RED

- [ ] Add only the six exact assertions in §5; do not change production code,
  imports or fixtures yet.
- [ ] Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py::test_atomic_cutover_has_one_source_and_entrypoint_topology \
  tests/unit/launcher/test_actor_environment.py::ActorEnvironmentBuilderTests::test_actor_workspace_contains_only_selected_projection

./buddyswitch-test focused \
  tests/process/package/test_distribution_install.py::test_atomic_cutover_distribution_contains_every_required_runtime_resource \
  tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_root_launcher_uses_only_verified_installed_package \
  tests/process/services/test_runtime_broker_lifecycle.py::test_broker_command_uses_only_installed_module_and_explicit_state_paths

./buddyswitch-test focused \
  tests/system/instance_lifecycle/test_environment_build_safety.py::TestEnvironmentBuildSafety::test_started_actor_is_code_free_and_runtime_attributable
```

- [ ] Record exact run IDs, intended failures and cleanup.

No implementation begins until all six claims discriminate the old topology.

### Task 3 — Move source/resources once

This begins the non-runnable internal mutation window. Tasks 3–5 are one
implementation block; do not claim or hand off an intermediate checkpoint.

- [ ] Apply exactly 223 moves and 5 deletes from the frozen map. A bulk exact
  `git mv`/mechanical move is permitted; content edits use `apply_patch`.
- [ ] Create only the five target package `__init__.py` owners named in the
  consumer manifest.
- [ ] Add `assets/**/LICENSE*` to the launcher package-data allowlist.
- [ ] Rewrite moved imports to `buddyswitch...` absolute imports or explicit
  same-package relatives.
- [ ] Replace manifest/profile/Skill/contract/schema/Web asset lookups with
  installed package resource access.
- [ ] Remove top-level `env`, `runtime_kernel`, `env_manifest`,
  `env_profiles`, `runtime_skills`, `turn_runtime`, `artifact_selection`,
  `browser_evidence`, `env_cleanup` and `output_schema` imports.
- [ ] Move the test-only output schema validator and rewrite its tests.
- [ ] Update root test support/imports for installed package modules without
  adding source `PYTHONPATH`.
- [ ] Prove mechanically: 228 classified, 223 targets unique, five deletes
  absent, no old input file remains.

Do not add import aliases, `sys.modules` bridges or source loaders.

### Task 4 — Cut public and child processes

- [ ] Add the fourteen new thin entrypoint modules in the frozen allowlist.
- [ ] Add one process-runtime invocation helper that calls the accepted
  `verify()` owner and maps `RUNTIME_UNAVAILABLE`/`RUNTIME_MISMATCH` before an
  owner runs.
- [ ] Make both root wrappers resolve only runtime dir, activation record and
  deterministic `venv/bin/python`.
- [ ] Make `tests/runner.py` verify the installed runtime before discovery,
  clear source `PYTHONPATH`, and assert `buddyswitch.__file__` is below the
  activated package root.
- [ ] Change every production child Python command to
  `<sys.executable> -m <allowlisted entrypoint>`.
- [ ] Remove Broker/Env MCP/dispatcher `--repo-root`, checkout `.py` execution
  and dynamic file loading.
- [ ] Resolve any still-current shell helper from installed package resources;
  shell-to-shell references are relative to the installed shell directory.
- [ ] Use activation `source_root` only for the external `projects/app` seed.
  Replace production `BUDDYSWITCH_REPO_ROOT` with explicit project/state
  locators; do not retain it as an alias.
- [ ] Emit the same activation identity in Broker/App/central Daemon/instance
  Daemon/Browser status and startup logs. Store that exact record on new Actor
  creation/start.
- [ ] Update tests/fakes to execute installed modules. Test-only fake Codex may
  `cd` to the repository to import root test support; it may not add
  implementation source roots to `PYTHONPATH`.

`BUDDYSWITCH_PYTHON` may remain only as a derived projection of the verified
runtime interpreter for current installed shell helpers/tests; it is never an
independent override or fallback.

### Task 5 — Replace Actor implementation publication

- [ ] Remove `repo_root`, `RUNTIME_COPY_PATHS`, runtime-copy staging and all
  workspace validation that expects copied source.
- [ ] Supply explicit project/shared/instance/auth locators and verified
  runtime identity.
- [ ] Load Role AGENTS, selected Skills, catalog and contracts from installed
  package resources.
- [ ] Publish exactly the allowlist in the consumer manifest.
- [ ] Generate Env MCP/diagnostics configuration with installed module
  entrypoints and the verified interpreter.
- [ ] Update moved Role/Skill guidance that must work inside the code-free
  Actor.
- [ ] Preserve preflight no-write, atomic publication, post-publication
  attributable failure, shared-project seed-once and deletion safety.
- [ ] Rewrite Actor/unit/process/system fixtures to the new logical builder
  inputs; do not recreate fake old repositories inside Actor roots.

At the end of Task 5 the source candidate must contain one path, but no GREEN
claim is allowed until a fresh wheel is installed and activated.

### Task 6 — Build, install and activate the candidate

- [ ] Confirm no BuddySwitch process owns the checkout runtime.
- [ ] Build one clean wheel through `pyproject.toml`.
- [ ] Install it non-editably into the checkout-local runtime using the
  explicit provisioning path; never install from a launcher or Actor start.
- [ ] Activate it against the exact current source and verify status.
- [ ] Record wheel manifest/digest, activation identity and installed package
  root.
- [ ] Assert the installed package exactly corresponds to source, all seven
  representative resources ship, and tests/cache/bytecode do not.
- [ ] Assert `buddyswitch` resolves from the installed venv with empty source
  `PYTHONPATH`.

If install/activation fails, retain the exact evidence and stop. Do not make a
launcher fallback or weaken correspondence.

### Task 7 — Turn the six cross-boundary proofs GREEN

- [ ] Re-run the three exact §5 commands.
- [ ] Require all six assertions to pass with clean run roots.
- [ ] Run the accepted C1 group:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/process/package
```

- [ ] Close F-037 only as a proposal in the return packet after the four exact
  licenses and activation correspondence pass.

### Task 8 — Prove package/import/resource behavior

- [ ] Run:

```bash
./buddyswitch-test focused tests/unit
./buddyswitch-test focused tests/unit/web/asset_contract_javascript.test.js
./buddyswitch-test focused tests/integration
```

- [ ] Fix only namespace/resource/locator consequences inside frozen scope.
- [ ] Stop if a test demands a changed Tool, command, lifecycle or persisted
  semantic contract.
- [ ] Record run IDs, counts, durations and cleanup.

### Task 9 — Prove every process and lifecycle consumer

- [ ] Run:

```bash
./buddyswitch-test focused tests/process
./buddyswitch-test focused tests/system
```

- [ ] Require terminal agreement for start/clear/resume failures: persisted
  status, protocol result, consumer-visible result, error attribution and
  cleanup agree.
- [ ] Through isolated test state, capture one public path:

```text
instance roles
instance start
instance status/list
representative Tool request
input
clear
stop
resume
stop
delete
```

- [ ] Record Actor ID, thread/runtime/process identities, exact workspace
  allowlist and final absence of process/socket/PID/lock/temp state.
- [ ] Do not access or mutate canonical user data for manual proof.

### Task 10 — Return at the C5 gate

- [ ] Confirm every old source file in the 228 manifest is absent.
- [ ] Scan executable source/tests/packaged Role/Skill guidance for retired
  imports, source `PYTHONPATH`, checkout `.py` execution, `--repo-root`
  loading, `RUNTIME_COPY_PATHS`, dynamic source loading and workspace
  implementation.
- [ ] Classify only negative guards and historical coordinating memos as
  allowed occurrences.
- [ ] Run `git diff --check`.
- [ ] Confirm index empty, no commit/branch change and no generated build/test
  residue or live process.
- [ ] Update the executor state and return the exact result schema from the
  Goal Packet.
- [ ] Stop. Do not edit current root guidance, run `full`, perform C6, stage or
  commit.

## 7. Stop conditions

Stop immediately and retire the packet if:

- source/partition/consumer identity disagrees;
- a public behavior or semantic owner must change;
- a production process outside the allowlist exists;
- an Actor needs copied implementation;
- canonical data needs migration/coexistence;
- a compatibility import, source fallback or second runtime appears
  necessary;
- current guidance must change to make C2–C5 executable rather than merely to
  document the final path;
- a direct proof cannot observe the claimed path;
- unrelated dirty work overlaps a required write.

Return evidence and a replan proposal. Do not solve an architecture question
inside the executor task.

## 8. Explicit non-goals

- C6 root `README.md`, `AGENTS.md`, `docs/arch/**` and final residue update;
- `./buddyswitch-test full`;
- S2 Demand or any product module semantic relocation;
- RoleHost/plugin architecture;
- package versioning or multi-runtime management;
- canonical user-data relocation;
- commit, stage, branch, PR or merge.
