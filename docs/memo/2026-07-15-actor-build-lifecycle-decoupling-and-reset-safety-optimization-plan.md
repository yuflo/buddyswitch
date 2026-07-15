# Actor Build Lifecycle Decoupling And Reset Safety Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute inline with `superpowers:executing-plans`, use `superpowers:test-driven-development` for every behavior change, and use only `./buddyswitch-test focused <explicit-target>...` until the final acceptance scope is explicitly selected.

**Goal:** Finish the worktree-to-copy migration by keeping actor construction inside the build pipeline, removing build/source-repository validation from actor lifecycle commands, and making shared-root reset reject symlinks before any filesystem mutation.

**Architecture:** `ActorEnvironmentBuilder` owns only first-time materialization and pre-publication validation. Lifecycle commands locate an existing actor deterministically from `BUDDYSWITCH_SHARED_ROOT + actor_id`, validate its instance record/runtime identity, and operate on runtime processes without entering the builder or rereading build inputs. Reset owns only `.codex-buddyswitch`; it rejects a symlink/non-directory root before acquiring the root-local runtime lock and revalidates under the lock before deletion.

**Tech stack:** Python 3.13, Bash HostControl, pathlib/lstat, unittest, BuddySwitch focused runner, real `buddyswitch-codex` and Codex CLI acceptance.

---

## Scope and fixed decisions

1. This optimization finishes the current copy-based actor build migration. It does not redesign the one-project application model.
2. Preserve the current `workspace/projects/app -> <shared-root>/project/workspace/projects/app` projection and its existing role/permission behavior.
3. Source repo content is a build input only. After publication, `resume`, `stop`, and `delete` must not call `actor_environment.py`, validate the source manifest/role template/project source, or repair build output.
4. The launcher code still executes from the current checkout in this milestone. Removing the installed CLI carrier from the checkout is a later deployment concern; lifecycle nevertheless must not consult source build inputs.
5. Build validation remains strict before atomic publication. Runtime-owned mutable paths, including real Codex temporary symlinks under `codex-home/tmp`, are not rescanned by lifecycle operations.
6. `.codex-buddyswitch` is a runtime/deployment root, never a repo target. Reset must return failure and leave the symlink target byte-for-byte/entry-for-entry untouched when the configured root is a symlink.

## Current root causes

- `instance_resume_locked` invokes `actor_environment.py --validate-existing`. That reuses the build staging validator across the complete live actor tree and rereads repo build inputs.
- The live actor tree is mutable after publication. Real Codex legitimately creates temporary symlinks, so staging invariants are false after runtime starts.
- `env reset --yes` acquires `${shared_root}/run/locks/runtime.lock` before validating the reset root. A symlink root is therefore followed and its target is mutated before reset logic runs.
- `buddyswitch_validate_reset_root` checks only the basename, and `buddyswitch_remove_owned_path` currently treats a symlink as a successful unlink operation.
- Existing tests use fake Codex and a normal reset directory; they did not model real Codex temporary symlinks or assert zero mutation of an external symlink target.

## File responsibility map

**Modify**

- `tools/launcher/actor_environment.py` — keep build-only API/CLI; remove `validate_existing` and `--validate-existing`.
- `tools/launcher/host_control.sh` — keep the sole builder call inside `start_locked_bootstrap`; make resume runtime-only and source-input-independent.
- `tools/launcher/env.sh` — make owned-root removal reject symlinks and strengthen locked reset root validation.
- `tools/launcher/cli.py` — perform no-follow reset preflight before the root-local lock can create files; skip locking/mutation when the root is absent.
- `tests/unit/launcher/test_actor_environment.py` — remove lifecycle expectations from builder tests; retain strict staging/build tests.
- `tests/process/cli/test_host_control.py` — lock the architecture boundary: exactly one builder call in start and none in resume/stop/delete.
- `tests/system/instance_lifecycle/test_environment_build_safety.py` — replace Git-bearing resume policy with runtime-symlink and detached-build-input lifecycle proof.
- `tests/process/launcher/test_public_cli.py` — add reset symlink zero-mutation regression and preserve normal reset behavior.
- `tests/unit/architecture/test_external_control.py` — assert lifecycle blocks do not reference the builder or source build validators.

**Preserve**

- `workspace/projects/app` shared projection.
- Existing copy allowlist, project seed-once behavior, staging cleanup, atomic publication, auth projection, and role skill installation.
- Deterministic locator: `<shared-root>/instances/<actor-id>/workspace` plus `instance.json` consistency checks.

## Task 1: Establish RED for lifecycle/build separation

**Tests:**

- `tests/process/cli/test_host_control.py`
- `tests/unit/architecture/test_external_control.py`

- [x] Extend the HostControl architecture test to extract `instance_resume_locked` and assert:

```python
self.assertNotIn("actor_environment.py", resume_block)
self.assertNotIn("--validate-existing", resume_block)
self.assertNotIn("buddyswitch_require_env_profile", resume_block)
self.assertNotIn("buddyswitch_require_role_agents_template", resume_block)
```

- [x] Assert `host_control.sh` contains exactly one `actor_environment.py` reference and that reference belongs to `start_locked_bootstrap`.
- [x] Run RED:

```bash
./buddyswitch-test focused \
  tests/process/cli/test_host_control.py::HostControlTests::test_host_control_start_has_one_builder_boundary_before_runtime_services \
  tests/unit/architecture/test_external_control.py::ExternalControlArchitectureTests::test_actor_environment_build_is_private_to_host_control
```

Expected: failure because resume still calls the builder and source role/profile validators.

## Task 2: Establish RED for the real runtime boundary

**Test:** `tests/system/instance_lifecycle/test_environment_build_safety.py`

- [x] Replace the two tests that require resume to reject a post-build `.git` directory. Build-time Git-free proof remains in builder/start tests; lifecycle no longer owns this invariant.
- [x] Add an active-resume regression that creates a representative runtime-owned symlink under `instance_root/codex-home/tmp/arg0/...`, calls `instance resume`, and expects the existing actor/thread to remain active.
- [x] Add an inactive-resume regression that starts/stops an actor, overrides `BUDDYSWITCH_REPO_ROOT` with an empty detached directory, resumes it, and expects the recorded thread to return active without any build repair.
- [x] Run RED:

```bash
./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
```

Expected: active resume fails on the runtime symlink and detached-input resume fails while source preflight/config patching remains in the lifecycle path.

## Task 3: Remove lifecycle entry into the builder

**Production:**

- `tools/launcher/actor_environment.py`
- `tools/launcher/host_control.sh`
- `tools/launcher/env.sh`

- [x] Delete `ActorEnvironmentBuilder.validate_existing()` and the internal `--validate-existing` CLI option/branch.
- [x] Delete the two builder unit tests that exercise `validate_existing`; builder tests continue to prove strict staging validation before publication.
- [x] Remove the `actor_environment.py --validate-existing` call from `instance_resume_locked`.
- [x] Remove `buddyswitch_require_env_profile` and `buddyswitch_require_role_agents_template` from resume; these remain start/build preflight only.
- [x] Keep resume runtime-only: bind the deterministic actor path, validate `instance.json` and recorded Codex runtime, require the recorded thread, return idempotently when app-server is already active, otherwise restart the existing runtime services and resume the recorded thread.
- [x] Do not rebuild, seed, sync, repair, recursively validate, or source-copy any actor/project path during resume.
- [x] Avoid repatching build/profile-derived Codex configuration during resume. The stopped actor retains the configuration published/patched during start, and stable runtime socket paths are recreated by their runtime owners.
- [x] Run the Task 1 and Task 2 targets to GREEN.

## Task 4: Establish RED for reset fail-closed

**Test:** `tests/process/launcher/test_public_cli.py`

- [x] Add `test_env_reset_rejects_symlinked_shared_root_without_touching_target`:
  - create an external target directory with a sentinel;
  - point a path named `.codex-buddyswitch` at the target;
  - run `buddyswitch-codex env reset --yes` with `BUDDYSWITCH_SHARED_ROOT` set to the link;
  - expect non-zero `INVALID_ARGUMENT`;
  - assert the link still exists;
  - assert the target entry list is exactly the original sentinel and contains no `run/locks`.
- [x] Run RED:

```bash
./buddyswitch-test focused \
  tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_env_reset_rejects_symlinked_shared_root_without_touching_target
```

Expected: current reset exits zero, unlinks the symlink, and creates lock files in the target.

## Task 5: Make reset reject unsafe roots before mutation

**Production:**

- `tools/launcher/cli.py`
- `tools/launcher/env.sh`

- [x] Add a Python reset preflight that operates on the un-resolved configured path, rejects a basename other than `.codex-buddyswitch`, rejects `Path.is_symlink()`, rejects an existing non-directory, and allows an absent root without creating it.
- [x] Call preflight in `_dispatch_env` before `_run_locked_shell_owner`; if the root is absent, return `{removed: false}` immediately.
- [x] Strengthen `buddyswitch_validate_reset_root` to reject a symlink or non-directory during locked revalidation.
- [x] Change `buddyswitch_remove_owned_path` so symlinks fail instead of being treated as successfully removed. Existing instance delete already performs its own root confinement/symlink checks and should remain green.
- [x] Run the exact reset regression to GREEN, then run direct reset/delete impact:

```bash
./buddyswitch-test focused \
  tests/process/launcher/test_public_cli.py \
  tests/process/launcher/test_instance_commands.py::TestInstanceCommands::test_instance_delete_rejects_symlinked_instance_root_without_touching_external_directory \
  tests/process/launcher/test_instance_commands.py::TestInstanceCommands::test_instance_delete_rejects_symlinked_shared_root_without_touching_target_instance
```

## Task 6: Focused IMPACT verification

- [x] Run compatible direct targets:

```bash
./buddyswitch-test focused \
  tests/unit/launcher/test_actor_environment.py \
  tests/process/cli/test_host_control.py \
  tests/unit/architecture/test_external_control.py \
  tests/process/launcher/test_public_cli.py \
  tests/process/launcher/test_instance_commands.py
```

- [x] Run system targets separately if the runner declares exclusivity:

```bash
./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
```

- [x] Search the final lifecycle boundary:

```bash
rg -n "actor_environment|validate-existing|buddyswitch_require_env_profile|buddyswitch_require_role_agents_template" tools/launcher/host_control.sh
```

Expected: the builder, env profile, and role template appear only in start/build code; lifecycle blocks contain none.

## Task 7: Real CLI Actor pressure test

- [x] Use an isolated `BUDDYSWITCH_SHARED_ROOT` and the installed real Codex executable/version.
- [x] Run `instance start --role pm`; record actor ID, thread ID, workspace path, process IDs, and source identity.
- [x] While active, confirm real Codex temporary symlinks are present when produced, then call `instance resume <actor-id>` and require success with unchanged actor/thread identity.
- [x] Run `instance input`, `instance status`, `instance stop`, `instance resume`, and `instance delete --yes`; require the same recorded thread after resume and actor-root removal after delete.
- [x] Run the symlinked-root reset attack against an external sentinel; require non-zero failure, preserved symlink, and zero target mutation.
- [x] Run normal `env reset --yes` against the isolated real directory and require owned-root removal.
- [x] Stop all spawned processes and remove exact isolated sockets/temp roots; verify no test-owned PID/socket/root remains.

## Task 8: Completion audit

- [x] Inspect the final diff and classify every changed/untracked file as original migration work, this optimization, or preserved review material.
- [x] Confirm every invariant under “Scope and fixed decisions” has direct code and test evidence.
- [x] Confirm `projects/app` sharing and role permissions were not redesigned.
- [x] Confirm no lifecycle path invokes the builder or source build validators.
- [x] Confirm reset symlink failure occurs before target mutation.
- [x] Confirm focused automated proof and real CLI proof share the final source identity or rerun invalidated exact targets.
- [x] Record exact commands, results, cleanup state, evidence identity, and residual risk in this memo.
- [x] Do not claim completion if any item is supported only by static intent or an unrelated passing suite.

## Progress

- [x] Root causes reproduced with real Codex and a symlinked reset root.
- [x] Product/architecture scope confirmed with the user.
- [x] Optimization plan written before optimization implementation.
- [x] Lifecycle/build RED recorded.
- [x] Runtime-boundary RED recorded.
- [x] Reset fail-closed RED recorded.
- [x] Production changes GREEN.
- [x] Focused IMPACT verification passed.
- [x] Real CLI pressure test passed and cleaned up.
- [x] Completion audit passed.

## Verification evidence

### RED — lifecycle/build separation

```text
state: RED
source: HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf; tracked-patch=257ceb37a7648cfa6e62414c21ca8f6bbe3f5c908ffeb9724bcbf2d71e8f15f8
command: ./buddyswitch-test focused tests/process/cli/test_host_control.py::HostControlTests::test_host_control_start_has_one_builder_boundary_before_runtime_services tests/unit/architecture/test_external_control.py::ExternalControlArchitectureTests::test_actor_environment_build_is_private_to_host_control
result: exit 1; 2 failed because host_control.sh contained two actor_environment.py references instead of one
proves: resume still crossed the builder boundary
cleanup: runner root removed
```

### RED — reset symlink fail-closed

```text
state: RED
source: same RED test-first worktree identity
command: ./buddyswitch-test focused tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_env_reset_rejects_symlinked_shared_root_without_touching_target
result: exit 1; current command returned 0 instead of required INVALID_ARGUMENT
proves: reset accepted and unlinked a symlink root instead of failing closed
cleanup: runner root removed
```

### RED — active and inactive resume runtime boundary

```text
state: RED
source: same RED test-first worktree identity
command: ./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
result: exit 1; 2 failed, 2 passed
failure 1: active resume rejected codex-home/tmp/arg0/.../apply_patch as an unexpected symlink
failure 2: inactive resume with detached build inputs tried to read detached-runtime-carrier/scripts/env
proves: resume reused build/source preflight against a live actor
cleanup: /private/tmp/bs-test-90555d2b-fwfazrue removed by runner
```

### GREEN / IMPACT — exact owners and direct contracts

```text
state: IMPACT
source: HEAD=625aa5d11b55e54fc9ad5636f5bc1419d75d8bdf; final executable tracked-patch=a942387ba478fe13bd48dce26378d754c47c776b04c65606a6fd29e9bb2ed436
environment: /Users/chen/miniconda3/bin/python; BuddySwitch isolated focused runner
command: ./buddyswitch-test focused tests/unit/launcher/test_actor_environment.py tests/process/cli/test_host_control.py tests/unit/architecture/test_external_control.py tests/process/launcher/test_public_cli.py tests/process/launcher/test_instance_commands.py
result: exit 0; 86 passed, 181 subtests passed
proves: builder build-only contract, one HostControl builder entry, reset/delete behavior, public CLI, architecture boundary
cleanup: /private/tmp/bs-test-23fa768f-q6usddbs removed

command: ./buddyswitch-test focused tests/process/launcher/test_bootstrap_config.py tests/unit/browser/test_ttl_config.py
result: exit 0; 20 passed, 8 subtests passed
proves: explicit browser TTL runtime preparation after removal of the stale actor-runtime-prep call
cleanup: /private/tmp/bs-test-9f5bb4a8-h2xxebxs removed

command: ./buddyswitch-test focused tests/system/instance_lifecycle/test_environment_build_safety.py
result: exit 0; 4 passed
proves: copy-built shared project behavior, normal reset, detached build-input inactive resume, active resume with runtime symlink
cleanup: /private/tmp/bs-test-1ff2c6fd-hcid7c0t removed

command: ./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
result: exit 0; 1 passed
proves: start/input/status/stop/resume/delete main lifecycle remains intact
cleanup: /private/tmp/bs-test-3786144f-7hzhu6ae removed
```

### Real CLI acceptance

```text
state: MILESTONE
source: same final executable identity as IMPACT
environment: codex-cli 0.144.4; isolated /private/tmp/bs-real-copy-GLBMtU/.codex-buddyswitch
operations: instance start --role pm; active resume; instance input; stop; inactive resume; stop; delete --yes; normal env reset --yes; symlink-root env reset --yes
result: exit 0
actor: act-pm-9167e2b2c8de
thread: 019f65c2-87b0-7200-ac17-87dcbfa2b69e preserved across both resumes
runtime observation: 3 real Codex symlinks present under actor codex-home/tmp while active
reset observation: normal root removed; symlink root returned INVALID_ARGUMENT, link survived, external target retained only sentinel.txt and gained no run/locks
cleanup: actor root removed; recorded app/broker/daemon PIDs not live; app socket absent; /private/tmp/bs-real-copy-GLBMtU removed
```

### Completion audit

```text
git diff --check: exit 0
host_control actor_environment.py reference count: 1, inside start_locked_bootstrap only
resume block: no builder, --validate-existing, env-profile validation, role-template validation, source copy, seed, sync, or repair
project contract: workspace/projects/app remains the shared project projection
reset contract: Python no-follow preflight occurs before root-local lock acquisition; locked shell revalidation and owned-path symlink rejection remain as defense in depth
residual cleanup: all recorded runner and real-CLI roots absent; no process for the accepted real actor remains
full suite: intentionally not run; the task requested focused implementation/acceptance proof, not a frozen repository-wide release candidate
residual risk: a hostile concurrent path swap between reset preflight and runtime-lock open is not modeled; the observed/static symlink-root defect is closed with zero target mutation
```
