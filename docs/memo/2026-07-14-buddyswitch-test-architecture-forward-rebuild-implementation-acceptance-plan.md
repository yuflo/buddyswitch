# BuddySwitch Test Architecture Forward Rebuild Implementation and Acceptance Plan

> Execution rule: use `superpowers:executing-plans` for the serial critical path. Use subagents only for the owner waves explicitly marked parallel after the shared support contract is green. Do not edit shared runner/support files from parallel waves.

**Goal:** rebuild BuddySwitch tests around four resource-cost tiers, exact run-owned cleanup, one serial public runner, and owner-focused verification. Remove flat topology, product test hooks, host-wide cleanup, giant mixed-owner suites, custom JavaScript harnesses, and migration-only gates without retaining wrappers or dual collection.

**Core deliverable:** the rebuild in Sections 3-8. Changed-file selection, pytest parallelism, real-browser automation, and CI are separate measurement-gated follow-ons in Section 9. They do not block the core rebuild and must not introduce another test entry.

**Assessment:** `docs/spec/2026-07-14-buddyswitch-test-architecture-assessment.md` contains the scan evidence. `docs/spec/` is intentionally ignored; this tracked memo contains every implementation decision and acceptance condition needed to execute the rebuild.

---

## 1. Decision Summary

The current bottleneck is not one eight-minute full suite by itself. It is the combination of:

- unsafe process/socket ownership, including host-wide browser process sweeps;
- full-service startup paid by tests that only assert local CLI or protocol semantics;
- 103 flat test files with no resource-cost boundary or canonical runner;
- repeated overlapping verification with no fixed focused/full contract;
- giant mixed-owner files and duplicated fake/runtime helpers;
- test-only behavior in production modules;
- JavaScript harnesses that report three files instead of 155 source cases.

The rebuild therefore makes these decisions:

1. Fix resource ownership first; no parallel test execution is allowed in the core rebuild.
2. Use four resource tiers: `unit`, `integration`, `process`, and `system`.
3. Put schema and architecture contracts under the owning `unit` directory; `contract` is a proof type, not a resource tier.
4. Expose only `./buddyswitch-test focused ...` and `./buddyswitch-test full`.
5. Make the runner a supervisor: cleanup still runs after failure, fail-fast, SIGINT, or SIGTERM.
6. Assert only resources owned by the current run. Host-wide snapshots are diagnostics, never pass/fail ownership inference.
7. Split only the measured hotspots and mixed-owner files. Do not enforce arbitrary repository-wide line limits.
8. Keep permanent gates positive and structural. Historical names and retired paths are checked once at final migration acceptance, then removed.
9. Preserve capabilities, not raw historical case counts. Duplicate and obsolete cases may be merged or deleted with a recorded replacement behavior.
10. Do not add impact-map machinery, result schemas, xdist, Playwright, or CI until their Section 9 trigger is met.

## 2. Verified Starting Point

The scan established:

- 100 Python `test_*.py` files and 3 JavaScript `*.test.js` files at `tests/` root;
- 1,452 collected Python tests, 234 `self.subTest` sites, and 155 JavaScript `test(...)` registrations;
- about 69,647 executable test/support lines;
- 15 executable test files at or above 1,000 lines, 6 at or above 2,000, and 2 at or above 5,000;
- 75 Python test files mutate `sys.path`;
- 25 dynamically load product code with `spec_from_file_location`;
- 31 use subprocesses and 47 use `TemporaryDirectory`;
- 98 derive repository root from `Path(__file__).parents[1]`, which will break when moved;
- 97 retain a direct `unittest.main()` entry;
- no pytest config, canonical runner, test dependency lock, impact map, CI workflow, or real-browser lane;
- at least 62 launcher tests call the full-service start helper directly;
- `test_buddyswitch_launcher.py` is 12,402 lines and one 222-test class;
- a passing full launcher-start test left three unowned Unix sockets;
- the audit observed 14,644 BuddySwitch sockets under `/private/tmp`, with only nine held by live processes at that moment;
- launcher and browser-cockpit test setup/teardown contain host-wide process matching and kill behavior;
- production code reads test-only environment/registry state;
- the runtime broker contains a timeout-as-success test path.

The socket count is a host observation, not a deletion list. The implementation must not delete or kill resources that predate its own run.

## 3. Target Architecture

### 3.1 Final topology

```text
tests/
  support/
    __init__.py
    paths.py
    environment.py
    processes.py
    network.py
    cli.py
    fake_cdp.py
    fake_codex/
      __init__.py
      main.py
      state.py
      rpc.py
      websocket.py

  unit/
    actor/
    architecture/
    browser/
    daemon/
    env_tool/
    im/
    runtime_protocol/
    task_sys/
    track/
    web/

  integration/
    app_server/
    browser/
    daemon/
    env_tool/
    im/
    runtime_broker/
    support/
    task_sys/
    web/

  process/
    cli/
    launcher/
    services/

  system/
    browser_lifecycle/
    cleanup/
    instance_lifecycle/

  runner.py
```

Final root-level `tests/test_*.py` and `tests/*.test.js` count is zero. There are no compatibility import files, symlinks, marker aliases, or old/new dual collection paths.

### 3.2 Resource tiers

| Tier | Allowed | Forbidden | Core scheduling |
|---|---|---|---|
| `unit` | same-process code, pure fake, schema/AST/import contracts, temp-file-local logic | child process, listener, product runtime startup, repository mutation | serial |
| `integration` | isolated temp state, loopback/thread server, fake external dependency, component collaboration | public launcher, multiple long-lived product services, shared runtime roots | serial |
| `process` | one CLI or one service process and its protocol | multi-service user flow, unregistered child process, shared fixed port | serial |
| `system` | public CLI, multiple services, lifecycle and signal behavior | user login state, real iMessage account, user Chrome session | cross-worktree exclusive, serial |

`unit/<owner>/contract` may be used for schema or architecture contracts. It does not become a fifth tier.

Permanent runtime enforcement for `unit` denies child-process creation and listener binding, including indirect product calls, through an autouse tier fixture. Import-boundary tests prevent unit tests from importing process/system harness modules. Repository-write purity is enforced through the isolated run root plus review of the explicit writable paths; it is not approximated by a generic string scanner.

### 3.3 Single public runner

Only these commands are public in the core rebuild:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

`focused` rules:

- requires at least one explicit Python file/nodeid or JavaScript file/name pattern;
- a JavaScript case uses `focused <one-file.test.js> --node-name-pattern '<regex>'`; reject this option unless exactly one JavaScript file and no Python target is selected;
- never expands the request to neighboring owners or a full tier;
- groups Python and Node targets only to invoke the correct built-in runner;
- acquires the system lock when any selected target is under `tests/system/`.

`full` rules:

1. unit Python and unit JavaScript;
2. integration;
3. process;
4. system;
5. shell syntax and diff hygiene.

It is serial and fail-fast between tiers. Fail-fast never skips supervisor cleanup or owned-resource verification.

`buddyswitch-test` is a thin Bash bootstrap: resolve repo root, source `tools/launcher/env.sh`, call `buddyswitch_env_init`, then `exec "$BUDDYSWITCH_PYTHON" tests/runner.py`. Selection and orchestration remain in `tests/runner.py`. README and AGENTS do not publish raw pytest/Node aliases after migration.

The core runner prints normal human-readable commands, pass/fail status, duration, and residual diagnostics. It does not persist a versioned JSON protocol, fingerprint worktrees, cache results, or define speculative machine error vocabularies.

### 3.4 Exact resource ownership

The runner creates one run context containing:

- a unique `run_id`;
- a system temporary root outside the repository;
- isolated `HOME`, `CODEX_HOME`, XDG, `TMPDIR`, state, workspace, shared, instance, and fake executable roots;
- an append-only owned-resource ledger;
- the runner PID and signal handlers;
- the common Git directory used for the cross-worktree system lock.

All resource-producing tests use `tests.support.processes` and `tests.support.environment`. The ledger records only resources actually created:

- PID, PGID, process start identity, and command;
- a finite cleanup strategy key plus serializable arguments needed by the supervisor after the pytest process is gone;
- owned socket, PID, marker, log, profile, temp-root, and worktree paths;
- listener address when a test starts a listener.

For public launcher commands, detached services are not direct children of the test helper. Before invoking `instance start`, the supervisor registers the sandbox's canonical PID/marker/socket/worktree descriptors, monitors them while the command runs, and persists PID/start identity as soon as each descriptor appears. `finally` performs one last descriptor reconciliation even if pytest is interrupted.

Cleanup strategies are a closed support-layer dispatcher, not Python callbacks: `central_daemon_stop`, `instance_daemon_stop`, `runtime_broker_stop`, `app_server_stop`, `browser_stop`, `terminate_owned_pgid`, and `git_worktree_remove`. Each ledger record contains the strategy and canonical context arguments. The runner can therefore perform the normal product stop after a pytest child has exited or been killed.

Cleanup order is:

1. verify every recorded PID/start identity before any stop path may signal it;
2. call the product's normal stop path only for a verified current identity;
3. TERM the exact still-live owned PGID after re-verifying start identity;
4. poll with a monotonic deadline;
5. KILL only the same still-live owned identity;
6. reap children;
7. remove only ledger-owned paths/worktrees;
8. restore environment and globals;
9. fail the run if an owned resource remains.

The runner repeats the same cleanup in `finally` and SIGINT/SIGTERM handling, so pytest teardown is not the only cleanup owner. It never scans the host to infer ownership.

Host-wide PID/socket/listener snapshots may be printed before and after a diagnostic run. Differences outside the run ledger do not fail the run and are never automatically removed.

The system lock path is under `git rev-parse --git-common-dir`, so all worktrees of the repository contend on one lock. Its file is a persistent inode: runners only `flock`/release the open FD, never unlink it, and never classify it as a residual. Fixed-port product semantics, including 9222 when unavoidable, run only under that lock. Other tests use port `0` or a parent-owned bound listener. The plan does not use a release-before-bind `PortLease` abstraction.

### 3.5 Production/test separation

Final production rules:

- `tools/` and `scripts/` do not read `BUDDYSWITCH_TEST_*`;
- central daemon behavior does not change because a test registry is present;
- `actor_session` builds its child environment from an explicit production allowlist;
- socket fallback identities include the owning instance/shared root, not only `actor_id`;
- normal stop and signal/finally paths share one cleanup owner for each service;
- runtime root test overrides and re-exports are deleted;
- test isolation is provided by normal environment/context inputs and fake repositories, not test-only production branches.

### 3.6 Durable gates

Keep only gates that describe the desired live architecture:

- all tests collect through the final four directories;
- owner modules obey explicit import directions;
- public JSON/schema/envelope contracts parse and match current owners;
- unit runtime policy blocks subprocesses and listeners;
- resource-harness tests prove exact ownership, signal cleanup, and residual failure;
- JavaScript tests use `node:test` and report case-level results.

Do not create a generic `source_scan.py` policy engine. Historical filenames, removed command strings, `unittest.main()`, old test hooks, root tests, and custom harnesses are one-time migration acceptance scans. They do not remain as permanent residue tests.

## 4. Scope

### Create

- `buddyswitch-test`
- `pytest.ini`
- `requirements-test.txt` with exact verified pytest version
- `tests/runner.py`
- generated during implementation: `docs/memo/evidence/2026-07-14-test-architecture/{python-nodeids.txt,javascript-cases.txt,subtest-groups.txt,migration-map.json}`
- `tests/support/**` listed in Section 3.1
- `tests/{unit,integration,process,system}/**`

### Modify as resource owners require

- `AGENTS.md`
- `README.md`
- `tools/launcher/central_daemon.py`
- `tools/launcher/central_daemon_core.py`
- `tools/launcher/daemon_core.py`
- `tools/launcher/daemon_mailbox.py`
- `tools/launcher/app_server.py`
- `tools/launcher/app_server.sh`
- `tools/launcher/actor_session.py`
- `tools/launcher/browser_runtime_manager.py`
- `tools/launcher/runtime_broker.sh`
- `scripts/runtime_kernel/server.py`
- `scripts/runtime_kernel/broker.py`
- `scripts/runtime_kernel/lifecycle.py`
- `scripts/env/repos/runtime_files.py`
- `scripts/env_store.py`
- every current root test through move, split, merge, or deletion

Product files are modified only where a RED lifecycle/isolation test proves the cleanup or test-coupling defect. This list is an ownership boundary, not permission for unrelated refactoring.

### Delete

- `tests/python_runtime.py`
- `tests/runtime_root_test_helper.py`
- `tests/helpers/fake_codex.py`
- `tests/test_buddyswitch_launcher.py` after its behaviors are split
- `tests/test_repo_consistency.py` after current positive contracts move
- `tests/test_im_boundary_residue.py`
- `tests/test_task_sys_rebuild_residue.py`
- all remaining root `tests/test_*.py`
- all remaining root `tests/*.test.js`
- product test registries, runtime-root override APIs, and their re-exports

### Not part of the core rebuild

- Superpowers/testing skill changes;
- a changed-file impact engine;
- pytest-xdist or any other parallel runner;
- persistent test-result JSON or cross-run cache;
- Playwright/Chromium installation and real-browser automation;
- a new CI workflow;
- real Codex login, real iMessage account, or user Chrome state;
- rewriting historical dated memos.

## 5. Migration Integrity

Historical counts are audit evidence, not a compatibility contract. The rebuild preserves the behavior capability matrix below:

| Capability | Fast proof | Collaboration proof | Lifecycle proof |
|---|---|---|---|
| CLI/envelope | parse, validation, error mapping | seeded-state command | public start/status/stop path |
| daemon/mailbox | protocol, routing, state | loopback mailbox/central daemon | signal and socket cleanup |
| runtime broker | frame, identity, deadline policy | server/client/coordinator | launcher handoff and stop |
| app server | DTO/WebSocket helpers | client and fake Codex | one process lifecycle |
| env tools | schema, validation, access rules | temp repository/service | selected black-box command |
| IM | routing, identity, reply projection | fake channel/HTTP loop | no real account in core |
| Web | renderer and state reducer | HTTP/API with fake CDP | browser process lifecycle with fake Chrome |
| task/track/artifact | domain rules | temp store/repository flow | selected CLI boundary |
| Git/worktree | path and safety rules | temp repository | create/delete system path |

At the start, save generated Python nodeid, JavaScript registration, and `subTest`-group snapshots under the tracked dated evidence directory listed in Section 4. These are historical migration evidence, not live suite inputs or compatibility gates.

During migration, Appendix A is the only human owner queue. `migration-map.json` is generated/updated by a one-time migration tool and covers every baseline group. A simple moved file may map at file level. Every measured hotspot or split/merged/deleted file maps each old class/nodeid prefix and `subTest` group to new targets plus disposition. Final verification rejects an unmapped baseline group. Raw case-count equality is not required; unexplained capability loss is forbidden. The generator/checker is removed after acceptance; the dated evidence remains reviewable history and is never collected as a test.

## 6. Implementation Plan

### Task 1: Build the serial runner supervisor and fix P0 lifecycle ownership

**Create:**

- `buddyswitch-test`
- `requirements-test.txt`
- `pytest.ini`
- `tests/runner.py`
- `tests/support/__init__.py`
- `tests/support/paths.py`
- `tests/support/environment.py`
- `tests/support/processes.py`
- `tests/support/network.py`
- `tests/integration/support/test_run_supervisor.py`

**Modify where RED tests require:** the production resource-owner files in Section 4, plus the two current test files that perform host-wide browser cleanup.

1. Create `requirements-test.txt` with the exact pytest version proven on Python 3.13 and create the minimal `pytest.ini`; do not add xdist. Run a clean install/preflight before any RED test.
2. Generate and track the baseline nodeid, JavaScript case, `subTest`-group, and initial migration-map evidence from the unchanged suite. Verify its 100 Python + 3 JavaScript file coverage before moving a test.
3. Write RED tests for exact PID/PGID/start-identity registration, serializable cleanup strategy dispatch after the pytest child is killed, identity-before-stop cleanup, stale/reused PID refusal, TERM/KILL/reap, runner `finally`, SIGINT/SIGTERM, owned-path cleanup, persistent common-dir locking, and residual failure.
4. Implement `paths.REPO_ROOT` once and make the runner pass a run context to support. Do not expose this context to production as a test branch.
5. Implement the thin bootstrap and serial `focused` mode first. During migration it may run explicit old or new targets; it never adds a compatibility import path. Preflight rejects unsupported Python, missing pytest, missing Node, or missing `node:test` with a direct environment error.
6. Add `full` orchestration that discovers the current test locations during the rebuild and the four final directories after cutover. The final topology test rejects root tests.
7. Write lifecycle RED tests for central daemon, instance mailbox, app server, broker, browser process, normal stop, SIGTERM, start failure, and long-path fallback sockets. For every service, a stale PID file pointing at an unrelated live process must never cause stop/start repair to signal that process.
8. Add a black-box RED test that SIGTERMs the runner while public `instance start` is in progress; descriptor reconciliation and persisted cleanup strategies must discover, normally stop, and clean every detached service.
9. Add resolver contracts proving shell and Python produce the same fallback socket, two roots with the same actor produce different sockets, and marker/status/ensure/stop use the same path.
10. Remove `BUDDYSWITCH_TEST_PROCESS_REGISTRY` behavior from central daemon code.
11. Change app-server and broker fallback identity to include the owning instance/shared root in both shell and Python resolvers; verify other fallback sockets are root-unique.
12. Make every production stop/start-repair path validate PID start identity before signalling and make normal stop and signal/finally share cleanup ownership for PID/socket/marker files.
13. Delete host-wide browser process sweeps and global `TemporaryDirectory` replacement immediately. Do not retain an old cleanup fallback.
14. Add a two-worktree competition test for the persistent common-dir lock, including a waiter that opened the lock before the first holder exits.
15. Run the resource-harness and lifecycle slice three times serially. Every run must have zero ledger-owned residuals.

Clean bootstrap and migration verification use the repository Python explicitly:

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && \
"$BUDDYSWITCH_PYTHON" -m pip install -r requirements-test.txt && \
"$BUDDYSWITCH_PYTHON" -c "import sys, pytest; assert sys.version_info[:2] == (3, 13)" && \
node -e "require(\"node:test\")"'

bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD:$PWD/scripts:$PWD/tools/launcher" \
"$BUDDYSWITCH_PYTHON" -m pytest <explicit-targets> -q -p no:cacheprovider'
```

This raw command is migration-only. It is removed from live README/AGENTS guidance when Task 5 completes.

**Checkpoint:** resource lifecycle review must pass before Tasks 3A-3D may run in parallel.

### Task 2: Consolidate paths, environment, fakes, and local protocol helpers

**Create:**

- `tests/support/cli.py`
- `tests/support/fake_cdp.py`
- `tests/support/fake_codex/{__init__,main,state,rpc,websocket}.py`
- focused support tests under `tests/unit/support/` and `tests/integration/support/`

1. Replace all 98 local `Path(__file__).parents[1]` roots with `tests.support.paths.REPO_ROOT` before moving files.
2. Remove test-local `sys.path.insert/append` and product `spec_from_file_location` loading. The runner owns one import environment: repo root, `scripts`, and `tools/launcher`.
3. Consolidate only helpers repeated across at least three owners: executable writing, fake Chrome/CDP, WebSocket framing, monotonic readiness, PID identity, and CLI JSON parsing.
4. Split the 1,154-line fake Codex into the listed cohesive modules and switch all consumers in the same change. Delete the old file; no import shim.
5. Use port `0` or a parent-owned listener. Do not create a reserve-then-release port helper.
6. Convert shared fixed sleeps to monotonic-deadline polling. Do not turn retries into silent success.
7. Verify every direct support consumer with `focused`; do not run full yet.

### Task 3: Rebuild the four tiers and split measured hotspots

Tasks 3A-3D may run in parallel only after Tasks 1-2 are green and the migration map assigns every Appendix A source file to exactly one `wave_owner`. Ownership follows the old source file, not the destination tier: the same owner performs every unit/integration/process/system split from that source. No second agent edits that old file or its destination files. The serial coordinator alone edits shared support, `pytest.ini`, `tests/runner.py`, topology gates, and the migration evidence.

Each source owner applies the same classification rules:

- same-process behavior, schemas, AST/import contracts, JavaScript reducers/renderers, and protocol primitives -> `unit`;
- isolated component collaboration with temp state/loopback/fake dependency -> `integration`;
- one CLI or one service -> `process`;
- public multi-service lifecycle -> `system`.

Every child process uses `tests.support.processes`. CLI syntax, validation, canonical JSON, unknown command, and seeded-state reads must not start the full service stack. Every moved group updates the generated migration map before its old file is deleted.

#### Task 3A: Runtime and daemon source wave

Own all source files centered on central/instance daemon, mailbox, runtime broker, app server, host control, turn runtime, and their protocol contracts. This wave alone splits `test_runtime_broker.py`, `test_app_server_client.py`, and `test_daemon_core.py` across the four tiers.

Replace `RuntimeWorkspaceTestMixin` consumers in these sources with normal environment/context setup or fake repositories. Fix the incomplete-frame timeout-as-success case by sending a complete invalid frame or explicit half-close and asserting a deterministic response.

#### Task 3B: Launcher, CLI, worktree, and browser-lifecycle source wave

Own `test_buddyswitch_launcher.py`, browser launcher/runtime/lazy-release sources, cleanup-system sources, black-box CLI sources, sandbox/profile preparation, and worktree lifecycle. Split the launcher by its existing behavior boundaries, writing all required destination tiers from this one wave.

Retain only the minimum true multi-service paths in `tests/system/`:

- start -> input -> status -> stop -> delete;
- start failure cleanup;
- clear/resume/attach continuity;
- browser acquire/release/restart with fake Chrome;
- Git worktree safety;
- reset cleanup;
- required signal/child termination timing.

All local CLI/protocol assertions move down to unit, integration, or process. Do not copy the old shared helper block into destination files. Delete the giant source file after its last mapped group moves.

System runs acquire the Git-common-dir lock. Tests do not write shared `projects/app` sentinels; worktrees and names are run-id scoped and ledger-owned.

#### Task 3C: Env, IM, actor, task, track, artifact, and identity source wave

Own the remaining domain sources for env tools, actor/session, IM, task system, track, artifact, evidence/search/message tools, identity, notifications, and role authorization. This wave alone splits `test_artifact_env_tool.py`, `test_imessage_channel.py`, and `test_env_tool_response_contract.py`.

Delete the two residue sources after their current positive replacement behaviors are mapped. `test_repo_consistency.py` is assigned from the start to the serial coordinator because it crosses owners; no parallel wave edits it.

#### Task 3D: Web and JavaScript source wave

Own `test_web_management.py`, `test_browser_cockpit_proxy.py`, `test_cdp_browser_session.py`, market-browser evidence, Web/IM projection, and all three JavaScript sources. Convert JavaScript to built-in `node:test`; it must report the 155 source cases individually before intentional mapped merges.

Split UI state by roster/capability/track/selection/create/lifecycle/refresh/IM/task and Web Python behavior by service/HTTP/API owner. Fake DOM/CDP remains unit/integration proof, not real-browser proof.

#### Serial Task 3E: Cross-wave topology closeout

After all source waves finish, the coordinator:

1. verifies every Appendix A file has exactly one owner and no unfinished migration group;
2. places current positive repo-wide schema/import contracts under `tests/unit/architecture/` and deletes historical scans;
3. adds the unit autouse runtime policy and proves it catches indirect subprocess/listener attempts;
4. resolves destination-name collisions without moving source ownership between agents;
5. runs every owner focused, then the four tiers serially.

### Task 4: Remove production test coupling and old topology

1. Replace `actor_session` test-prefix filtering with an explicit production child-environment allowlist.
2. Delete runtime-root override setters/resetters, re-exports, mixins, and last consumers.
3. Confirm no product module changes semantics based on `BUDDYSWITCH_TEST_*`.
4. Delete every migrated root test in the same change that creates its replacement. No root file may import a destination test.
5. Delete old helpers and historical residue tests listed in Section 4.
6. Add permanent topology/import/schema/resource tests described in Section 3.6.
7. Run focused verification for each owner, then run unit, integration, process, and system serially once.

### Task 5: Finalize the one runner and live guidance

1. Make final `full` discover exactly the four tiers and JavaScript unit files once each.
2. Make `focused` reject missing/invalid targets and preserve exact selection. Contract-test the one-JavaScript-file `--node-name-pattern` rule and prove it executes only the matching case.
3. Ensure runner cleanup executes on success, test failure, invalid target after context creation, SIGINT, and SIGTERM.
4. Keep system locking cross-worktree and fail clearly when held; do not silently wait forever.
5. Update README and AGENTS to publish only `focused` and `full`.
6. Remove migration raw commands from live guidance.
7. Run shell syntax and `git diff --check` through `full`; do not add another public wrapper.

### Task 6: Performance and no-residue acceptance

1. Run the final one-time residue scans in Section 7.
2. Establish the initial stability baseline by executing representative resource slices and final `full` three times on the same machine. After that baseline exists, reverify later changes with the smallest affected slice three times and one final `full`; add more full runs only after a failure, residue, or instability signal.
3. Record median tier/full durations and `--durations=25` output in the implementation memo or PR evidence.
4. Confirm local CLI/protocol tests no longer pay a full-service start and unit/integration tests do not use production timeouts as a passing path.
5. Obtain independent coverage, lifecycle, execution-order, and simplicity reviews.

## 7. Verification and Acceptance

### 7.1 Focused resource proof

```bash
./buddyswitch-test focused tests/integration/support/test_run_supervisor.py
./buddyswitch-test focused tests/process/services/test_central_daemon_lifecycle.py
./buddyswitch-test focused tests/system/instance_lifecycle
./buddyswitch-test focused tests/unit/web/ui_state_selection_refresh.test.js --node-name-pattern 'actor selection'
```

Run each resource-producing target three times. Hard assertions cover only the current run's ledger. Expected: no owned PID, PGID, child, socket, listener, marker, lock FD, temp root, or worktree remains. The persistent common-dir lock inode remains present and unlocked.

### 7.2 One-time migration residue scans

```bash
find tests -maxdepth 1 -type f \( -name 'test_*.py' -o -name '*.test.js' \)
rg -n 'sys\.path\.(insert|append)|spec_from_file_location|unittest\.main' tests
rg -n 'BUDDYSWITCH_TEST_|set_runtime_root_override|reset_runtime_root_override' tools scripts
rg -n 'tests/(test_buddyswitch_launcher|test_repo_consistency|runtime_root_test_helper|helpers/fake_codex)' . \
  -g '!docs/spec/**' -g '!docs/memo/**' -g '!**/__pycache__/**'
```

Expected: no matches. These scans are acceptance evidence only and are not copied into a permanent historical-blacklist test.

### 7.3 Capability and collection proof

- Appendix A has no unfinished file.
- generated baseline evidence remains tracked and readable by an independent reviewer;
- the migration-map checker proves every baseline file and every hotspot class/nodeid-prefix/`subTest` group has exactly one moved/merged/deleted disposition and replacement capability/target;
- Section 5 capability matrix has unit/integration/process/system proof where applicable.
- pytest collects only the final four directories.
- Node reports real case-level results through `node:test`.
- No test is collected from an old and new path.

### 7.4 Full proof

```bash
./buddyswitch-test full
```

Expected:

- four tiers execute once, serially, in order;
- failure stops later tiers but still performs cleanup and residual verification;
- Python uses `$BUDDYSWITCH_PYTHON`;
- unit/process/system boundaries remain intact;
- shell syntax and diff hygiene pass;
- no run-owned resource remains.

### 7.5 Efficiency proof

Before Task 3, remeasure on the same machine:

- one pure CLI/envelope slice;
- runtime-broker protocol/client slice;
- one central-daemon process lifecycle slice;
- one full launcher start/stop system slice;
- current serial full suite.

After Task 5, run the behavior-equivalent final targets three times and compare medians. Acceptance requires:

- pure CLI/envelope proof starts zero product services;
- unit tests use no product timeout as success;
- full-service startup is limited to the enumerated system paths, not duplicated across local CLI cases;
- focused medians do not regress from their behavior-equivalent baseline;
- final serial full median is at least 25% below the remeasured baseline;
- no speed target is achieved by skipping a capability, weakening an assertion, increasing a timeout, or suppressing a leak.

If the 25% full target fails, the rebuild is not declared complete. Use the final duration report to fix the largest remaining repeated startup or timeout. Do not enable xdist as the first response.

### 7.6 Definition of Done

The core rebuild is complete only when:

1. P0 lifecycle tests prove exact run-owned cleanup under success, failure, SIGINT, and SIGTERM.
2. Host-wide kill sweeps and global temp-directory replacement are deleted.
3. Production test registries, test-prefix branches, and runtime-root overrides are deleted.
4. Tests live only under `unit`, `integration`, `process`, and `system` plus shared support.
5. `buddyswitch-test` is the only live public entry and is serial.
6. The measured hotspots are split by owner/resource responsibility.
7. Tracked baseline/migration evidence covers every source and hotspot group; current capabilities remain proven and duplicate/obsolete cases have explicit dispositions.
8. JavaScript uses `node:test` with case-level reporting.
9. Permanent gates describe current architecture, not migration history.
10. Residue scans, three serial full runs, efficiency acceptance, and four independent reviews pass.

## 8. Current Owner Queue (Appendix A)

This is the single migration queue, based on each current file's highest real dependency. It is not a promise to preserve raw case counts. Mixed files must split; deleted or merged behavior must be recorded against this queue.

### Unit target (39 files, including 3 JavaScript files)

```text
tests/test_actor_capability.py
tests/test_actor_session.py
tests/test_actor_side_thread.py
tests/test_artifact_selection.py
tests/test_browser_page_expired_handler.py
tests/test_cli_contract.py
tests/test_codex_runtime.py
tests/test_daemon_communication_boundary.py
tests/test_daemon_contracts.py
tests/test_daemon_core_decoupling.py
tests/test_daemon_state.py
tests/test_daemon_trigger_router.py
tests/test_env_manifest_v2.py
tests/test_env_native_mcp_server.py
tests/test_env_tool_active_task_gate.py
tests/test_env_tool_identity.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_semantic_contract.py
tests/test_external_control_architecture.py
tests/test_im_actor_delivery.py
tests/test_im_boundary_residue.py
tests/test_im_delivery.py
tests/test_im_wake_handler.py
tests/test_instance_daemon_entrypoint.py
tests/test_notification_center.py
tests/test_output_schema_boundaries.py
tests/test_repo_consistency.py
tests/test_role_action_auth.py
tests/test_runtime_skills.py
tests/test_side_thread_registry.py
tests/test_task_management_skill_architecture.py
tests/test_task_sys_daemon_adapter.py
tests/test_task_sys_rebuild_residue.py
tests/test_task_sys_runtime_client.py
tests/test_task_sys_runtime_executor.py
tests/test_track_comments_repo.py
tests/web_management_markdown_renderer.test.js
tests/web_management_ui_contract.test.js
tests/web_management_ui_state.test.js
```

`test_im_boundary_residue.py` and `test_task_sys_rebuild_residue.py` are deleted. `test_repo_consistency.py` contributes only current positive contracts.

### Integration target (41 files)

```text
tests/test_app_server_client.py
tests/test_artifact_env_tool.py
tests/test_browser_cockpit_proxy.py
tests/test_cdp_browser_session.py
tests/test_communication_identity_cutover.py
tests/test_context_binding_env_tool.py
tests/test_daemon_core.py
tests/test_daemon_mailbox.py
tests/test_daemon_service_contract.py
tests/test_env_layer_end_to_end.py
tests/test_env_store_v2.py
tests/test_env_tool_payload_contract.py
tests/test_env_tool_response_contract.py
tests/test_evidence_env_tool.py
tests/test_external_im_projection_contract.py
tests/test_external_im_session.py
tests/test_external_query.py
tests/test_host_decision_surface_product_mode.py
tests/test_identity_global_convergence.py
tests/test_identity_product_ownership.py
tests/test_im_external_reply_loop.py
tests/test_im_http_router.py
tests/test_im_product_core.py
tests/test_im_web_management_projection.py
tests/test_imessage_channel.py
tests/test_market_browser_evidence.py
tests/test_message_tool_im_client.py
tests/test_run_env_tool.py
tests/test_runtime_actor_profile.py
tests/test_runtime_tool_feedback.py
tests/test_search_env_tool.py
tests/test_side_thread_lifecycle.py
tests/test_task_sys_checkpoint.py
tests/test_task_sys_side_processing.py
tests/test_task_sys_substrate.py
tests/test_track_comment_added_handler.py
tests/test_track_comment_env_tool.py
tests/test_track_env_tool.py
tests/test_track_owner_actor_model.py
tests/test_turn_integration.py
tests/test_web_management.py
```

### Process target (20 files)

```text
tests/test_black_box_tool_runtime.py
tests/test_browser_cockpit_launcher.py
tests/test_browser_runtime_manager.py
tests/test_buddy_env_profiles.py
tests/test_buddy_env_sandbox.py
tests/test_central_daemon_service.py
tests/test_clean_runtime_environment.py
tests/test_env_client_payload_cli.py
tests/test_env_layer_boundaries.py
tests/test_env_native_mcp_projection.py
tests/test_env_tool_package_independence.py
tests/test_env_tool_router.py
tests/test_fake_codex.py
tests/test_host_control.py
tests/test_memory_removal_contract.py
tests/test_prepare_runtime_context.py
tests/test_run_env_services.py
tests/test_runless_runtime_contract.py
tests/test_runtime_broker.py
tests/test_turn_runtime.py
```

`test_runtime_broker.py` must split: protocol/client behavior moves down; only one-service lifecycle remains process-level.

### System target (3 files)

```text
tests/test_browser_lazy_release_integration.py
tests/test_buddyswitch_launcher.py
tests/test_cleanup_system.py
```

All three split or merge into explicit system paths and are then deleted.

## 9. Measurement-Gated Follow-ons

These are independent upgrades, not unfinished core work. Each must use the same `buddyswitch-test` entry and replace its predecessor cleanly.

### 9.1 Changed-file selection

Trigger: after the core runner is used for at least ten real development tasks, review evidence shows repeated manual over-selection of integration/process/system tests.

Then add `changed --base <ref>` using a small owner map:

- all unit tests remain the fixed fast gate;
- only expensive integration/process/system owners are selected by source-owner glob;
- unmapped behavior source fails closed and prints the path;
- no import-graph engine, per-test reason prose, result JSON protocol, or full fallback;
- integrity checks enumerate behavior-source roots explicitly, including root `scripts/*.py`, `scripts/runtime_store/**`, `scripts/env/**`, `scripts/runtime_kernel/**`, `tools/launcher/**`, and Web assets.

### 9.2 Parallel execution

Trigger: after core acceptance, serial full still misses its target and duration evidence shows unit/integration CPU work, not process startup or timeout, is the dominant cost.

Then qualify one tier at a time with three serial and three parallel repetitions. Enable xdist only for a proven isolated tier, pin its exact version, and keep process/system serial. Parallelism is rejected if any owned-resource leak, shared root, port conflict, ordering dependency, or flaky retry appears.

### 9.3 Real-browser proof

Trigger: Web behavior that fake DOM/CDP cannot prove is selected as the next product risk.

Create one opt-in real-browser system slice with an explicit OS/Chromium binary contract. Before implementation, define a language-neutral ownership protocol or keep the browser owner entirely in Python; Node must not claim to reuse Python objects directly. The slice proves a minimal user flow and cleanup, then becomes part of `full` only after three clean serial runs. It does not use the user's Chrome profile or login state.

### 9.4 CI

Trigger: local core `full` is stable and the supported CI OS, Python 3.13, Node 24, and optional browser binary contract are decided.

CI performs a clean install from locked Python/Node dependencies and calls only `./buddyswitch-test`. It does not copy internal pytest, Node, or shell commands. CI addition does not create a second local execution contract.

## 10. Review Record

Three independent reviews were run against the first draft:

- specification/coverage review verified the 100 Python + 3 JavaScript inventory, 1,452 collected Python tests, and 155 JavaScript registrations, then rejected cross-language browser ownership, incomplete migration evidence, and ambiguous enforcement;
- execution review rejected the original task ordering, missing repo-root migration, absent runner-level cleanup, non-shared lock, fallback socket collision, and unavailable/misconfigured xdist dependency;
- simplicity/residue review rejected six all-at-once tiers, speculative impact/result protocols, arbitrary line gates, permanent historical scanners, and Playwright/CI/xdist as core blockers.

This revision resolves those findings by using four resource tiers, one serial two-mode runner, runner-level exact cleanup, a Git-common-dir lock, instance-root socket identity, one owner queue, capability-based migration acceptance, measured hotspot splitting, positive durable gates, and independent measurement-gated follow-ons.

The revised memo was re-reviewed for:

1. capability coverage and inventory completeness;
2. lifecycle/resource ownership correctness;
3. task dependency and command executability;
4. SHARP scope, no residue, and no dual-track compatibility.

All three independent reviewers returned `APPROVED`. No plan-level blocker remains.

## 11. Implementation Acceptance Record (2026-07-14)

### 11.1 Final collection and migration evidence

- Current serial collection: 386 unit tests / 1,132 subtests, 662 integration tests / 511 subtests, 233 process tests / 330 subtests, 16 system tests, and 155 JavaScript `node:test` cases.
- The tracked baseline contains 100 Python files, 3 JavaScript files, 1,452 Python nodeids, 155 JavaScript cases, and 234 `subTest` groups.
- The one-time migration checker covered all 103 baseline source files and all 1,042 required mapping groups. Dispositions are 794 moved, 108 merged, and 140 deleted. Every group has one disposition, a replacement capability, and an existing target in one of the four tiers; every deletion has an explicit reason. Checker result: zero errors.
- Broad duplicate launcher variants are recorded as intentional deletions against retained owner boundaries. The four high-risk launcher gaps identified during review have exact system regressions.

### 11.2 Repeated resource proof

All targets ran serially through `buddyswitch-test` three times on the same machine:

| Target | Results | Median runner duration |
| --- | --- | ---: |
| `tests/integration/support/test_run_supervisor.py` | 23 passed x3 | 5.22s |
| `tests/process/services/test_central_daemon_lifecycle.py` | 3 passed x3 | 0.35s |
| `tests/system/instance_lifecycle` | 11 passed x3 | 32.38s |
| JavaScript actor-selection pattern | 4 passed x3 | 0.06s |

Every run completed its exact ledger cleanup. The run root was removed, no recorded process identity remained, and the shared common-dir lock inode remained reusable.

### 11.3 Serial full-suite proof and efficiency

The three final `./buddyswitch-test full` runs passed in tier order with shell syntax and `git diff --check` green:

| Run | Unit | JavaScript | Integration | Process | System | Phase-sum total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.35s | 0.17s | 61.29s | 62.50s | 37.90s | 163.60s |
| 2 | 1.35s | 0.17s | 60.76s | 61.21s | 37.31s | 161.18s |
| 3 | 1.36s | 0.17s | 60.98s | 63.56s | 37.99s | 164.48s |
| Median | 1.35s | 0.17s | 60.98s | 62.50s | 37.90s | 163.60s |

The final `--durations=25` reports identify the current head of each tier: unit architecture checks at 0.08s; integration supervisor cleanup at 3.49s, runtime-broker identity refusal at 2.55s, and browser search protocol at 2.11s; process browser failure cleanup at 6.72s and browser status at 3.98s; system resume continuity at 6.89s, attach continuity at 5.20s, the complete main flow at 4.42s, and worktree reset safety at 3.94s. No passing path was obtained by increasing a production timeout.

The 163.60s median is 65.9% below the recorded approximately 480s pre-rebuild task-history baseline, exceeding the required 25% improvement. The historical suite was not rerun after deletion; the comparison uses the recorded same-machine baseline rather than reconstructing an unsafe compatibility path.

### 11.4 Final acceptance scans and reviews

- No root-level test file, dynamic import/path hack, product test hook, runtime-root override, or retired helper/launcher path matched the Section 7.2 scans.
- `tests/` contains only the four tiers, shared support, the package marker, and `runner.py`. The only direct `subprocess.Popen` calls below resource-producing tiers are the three support fixtures that deliberately exercise runner cleanup and pre-register their descriptors.
- The final simplicity review rejected a 1,553-line mixed launcher harness. It was deleted and replaced with a 358-line cross-tier primitive base, a 551-line process-only harness, and a 428-line system-only harness. Fifteen dead helpers were removed, system tests no longer import process-tier support, and a static call-site check reports zero dead methods in the three replacements.
- After that review fix, process launcher tests passed 89 tests / 39 subtests, system passed all 16 tests, and an additional full run passed every tier plus shell syntax and diff hygiene in a 160.11s phase sum.
- Final regressions moved `PYTHONDONTWRITEBYTECODE=1` ahead of the runner process itself and made the generated fake-Codex executable enforce the same rule even when its parent environment is sanitized. The final full run passed 386 unit, 661 integration, 233 process, 16 system, and 155 JavaScript cases in an approximately 162.7s phase sum; its exact root was removed and no repository bytecode cache remained.
- Capability coverage, lifecycle/resource ownership, execution ordering, and SHARP simplicity/residue review lenses returned `APPROVED` after their findings were fixed.

All Section 7 acceptance conditions and the Definition of Done are satisfied.

### 11.5 Efficient re-verification amendment

The initial full-suite x3 stability and performance evidence above remains the baseline. Follow-up audit fixes use the shortest risk-matched loop: affected lifecycle slices run three times, then the frozen tree runs one canonical `full`. A passing full is not repeated mechanically; additional full runs are required only when the first run fails, leaves residue, or exposes timing instability. This keeps verification test-bound without making the test-architecture rebuild depend on the inefficient behavior it is replacing.

The follow-up exact-identity audit added targeted ledger cleanup, immediate detached descriptor reconciliation, and LIFO descriptor teardown before temporary instance removal. The supervisor slice passed 24 tests x3; browser commands passed 17 tests / 5 subtests x3; the web lifecycle passed x3. Independent lifecycle review then found and verified the failure-path ordering fix. The first canonical full correctly exposed the same late-teardown issue in three system cases while unit, JavaScript, integration, and process were green. After moving all system service descriptors into the same LIFO cleanup boundary, those three exact regressions passed x3 and the complete instance-lifecycle slice passed 11 tests.

Per this amendment, one additional full was justified by that concrete failure signal. It passed 386 unit tests / 1,132 subtests, 155 JavaScript cases, 662 integration tests / 511 subtests, 233 process tests / 330 subtests, and 16 system tests. The phase-sum was approximately 156.2s; shell syntax and `git diff --check` passed; the exact run root was removed; repository bytecode and targeted residue scans were empty; lifecycle re-review returned `APPROVED`. No further full repetition was performed.
