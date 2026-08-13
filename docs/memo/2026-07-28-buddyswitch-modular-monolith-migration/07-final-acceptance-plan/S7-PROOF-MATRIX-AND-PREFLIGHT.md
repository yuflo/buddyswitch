# S7 Proof Matrix and Preflight

> Historical preflight evidence. S7 is accepted; see `S7-ACCEPTANCE.md`.

## Pre-READY evidence

### Architecture, replacement and distribution

```text
command:
  ./buddyswitch-test focused \
    tests/unit/architecture \
    tests/process/package/test_distribution_install.py \
    tests/process/package/test_runtime_activation.py
run:      5e822ce3503c46b7818bb447fc239a27
result:   163 passed, 85 subtests passed
duration: 27.10s pytest / 27.32s runner
cleanup:  clean
```

This group proves the one source/build owner, installed correspondence,
explicit composition, Foundation neutrality, module/Role boundaries, runner
topology and retired-root absence. It uses the current public runner and the
runtime identity in the source snapshot.

### Representative product and real-Actor paths

```text
command:
  ./buddyswitch-test focused \
    tests/system/instance_lifecycle/test_environment_build_safety.py::TestEnvironmentBuildSafety::test_directory_only_investor_role_starts_with_only_selected_bootstrap \
    tests/system/goal_mode/test_product_flow.py::NativeGoalProductFlowSystemTests::test_web_actor_delivers_then_goal_and_demand_complete
run:      9a85e5acda2846c6bd0a1b2e2b4ab9e5
result:   2 passed
duration: 208.59s pytest / 208.80s runner
cleanup:  clean
```

The first path starts the directory-only investor Role and proves its exact,
code-free selected bootstrap. The second crosses Web, IM, Demand triage, Task,
native Goal, delivery and Demand completion to one terminal consumer result.

### Source-equivalent repository baseline

Accepted S6 FINAL `56b2be7f071942b89ffecad5e2891bc9` passed on the same
verified executable source/distribution identity:

```text
Python unit:         528 passed, 861 subtests
JavaScript unit:     147 passed
Role-local contract: 8 passed
Integration:         771 passed, 460 subtests
Process:             248 passed, 366 subtests
System:              23 passed
total:               1,725 tests, 1,687 subtests
```

S7 nevertheless requires one new frozen `full` run because the claim is the
repository-wide final release candidate, not only S6 preservation.

## Acceptance proof matrix

| Proof class | Material claim | Direct evidence before READY | S7 exit evidence |
|---|---|---|---|
| Product | representative Role, Web/IM, Demand, Task/Goal, Track, Artifact, Communication, Search, Evidence, Context and Browser paths produce current results | real-Actor/product run `9a85e5a…`; accepted stage records; S6 FINAL | one new frozen FINAL containing every current tier |
| Contract | success, rejection, authority, persisted effect and terminal status agree across Tool, Daemon, Broker, Web/CLI and RoleHost | accepted stage exact/affected runs; architecture/package run `5e822ce…` | focused architecture/package GREEN plus FINAL |
| Architecture | one package/runtime, explicit module root, neutral Foundation, narrow RoleHost, code-free Actor and one runner | `5e822ce…` | same current targets rediscovered and green |
| Replacement | no retired root, alias, fallback, scanner, duplicate catalog, old test owner or current guidance path | `5e822ce…`; source snapshot | architecture/package proof, manual residue inventory and clean diff |
| Operations | startup, failure attribution, recovery and process/socket/lock/temp cleanup remain exact | `9a85e5a…`; prior Process/System evidence | frozen FINAL and terminal resource audit |

## Protected observable inventory

S7 changes no contract, so it relies on current assertions rather than adding
new tests. The representative paths can fail when their terminal loops break:

| Observable | Current assertion owner | Failure detected |
|---|---|---|
| reviewed Role starts with only selected AGENTS/Skills and no code | `test_directory_only_investor_role_starts_with_only_selected_bootstrap` | Role discovery, publication, runtime or cleanup break |
| external request becomes a completed delivered Demand through native Goal | `test_web_actor_delivers_then_goal_and_demand_complete` | Web/IM/Demand/Task/Goal/delivery terminal contradiction |
| source/install/runtime correspondence rejects drift | `tests/process/package/test_runtime_activation.py` | source, distribution, interpreter or record mismatch |
| clean wheel contains current owners and no retired Role/runtime roots/tests | `tests/process/package/test_distribution_install.py` | packaging or replacement drift |
| all owner/dependency/composition invariants | `tests/unit/architecture/**` | duplicate owner, upward dependency or retired live path |

## Contrary signal during preflight

One read-only shell inventory used `path` as a zsh loop variable and thereby
shadowed the shell command-search array; its final `find`/`sort` invocation did
not run. It changed no file, process or runtime state. The corrected probe used
`probe_path` plus absolute `/usr/bin/find` and `/usr/bin/sort`, found only the
inert Launcher root, no retired roots, no attributable process and a clean Git
state. S7 instructions therefore forbid repurposing `path`, `PATH`, `HOME` or
other system variables in probes.
