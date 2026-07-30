# S3 Task and Goal Boundary Cutover Acceptance

> Decision: `ACCEPTED`
> Execution packet: `BS-MM-S3-R1-20260730-01`
> Retired predecessor: `BS-MM-S3-20260729-01`
> Authority: coordinating hub
> Acceptance date: 2026-07-30
> Next stage: S4 preparation only

## 1. Accepted outcome

The S3 acceptance sentence is true:

> Task owns canonical Task state and native Goal convergence semantics in one
> component; Demand collaboration uses exact acyclic Public operations; no
> private cross-read, duplicate write path or Goal ownership confusion
> remains.

The accepted path is:

```text
application composition
  -> one passive Task assembly
    -> typed Tool / Daemon / CLI / Actor Console / cleanup contributions
      -> one Task-private state and native-Goal convergence owner
        -> Task Public for exact cross-component reads
```

Task creation receives the current Demand resolver through the Task-owned
`DemandSelectionResolver` port wired once by application composition. Task
imports no Demand source. Demand's two Task consumers import Task Public only.
No compatibility import, forwarding package, fallback owner, second writer or
alternate Task/Goal path remains.

## 2. Frozen candidate identity

The coordinating hub reproduced the executor return before writing this
acceptance record:

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch:
fea-tool

HEAD and origin/fea-tool:
baf20e80fbf0eb177be9cd90c65dc58f7615294c

tracked src/tests binary patch SHA-256:
512f4ed837383ed7d6d906d3a78037c9825ce50119fb1199573eb89f3d8fd9ef

tracked src/tests name/status SHA-256:
c425a3e2b7f1cf59633babb4f23853f645964e4f159ebf1aa1471b4a7edcfddf

complete binary patch SHA-256:
de1ee5fe29dbd16c05e3e080088ad1aa5bb541f0e4bfdf8408c63f84404878b3

complete name/status SHA-256:
ca1bb3f8f81df9063787509b18676fce02d900101d0c8ae6865176bb54296a71

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

tracked scope:
65 paths — 52 modified and 13 deleted

untracked source/test files:
30

untracked path-set SHA-256:
989ffcdf6b5c08190c19a991a8b33b5a7e534dd5ddfade46f909dc8594bcd658

untracked content-manifest SHA-256:
6e54964b96f41b82e8389d39f35db61e425ac5636bcd187d2ea2bb4f671b4130

git diff --check:
clean
```

No S3 file was staged, committed, pushed, reverted, stashed, reset or moved
by the executor. The acceptance documents are non-executable coordinating
truth written after this frozen executable identity.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| Tool `task_sys` remains exactly `list/get/create/cancel` | Actor Tool -> Task registration -> Task-private owner | focused architecture/contract run `886a28b515d048fdb9bc2fd367bde294`; FINAL `79c7f25e1c03484d9b600a85bd503712` | PASS |
| Task create validates current Demand before writing | Task Tool -> injected Demand Public resolver -> Task owner | Task-local integration and system Goal/Demand product flow in affected and FINAL evidence | PASS |
| Task/native Goal convergence and recovery remain exact | Daemon registration/mailbox -> Task Goal handler -> Task owner + App Server Goal API | affected run `38ad62540de645a6b8c08a1903dc53db`; FINAL | PASS |
| Demand attention and completion evidence use Task Public only | Demand adapters -> Task Public -> Task owner | affected unit/integration run `addf01ca26e24149b9f0b7b2e1d99301`; FINAL | PASS |
| public CLI and Actor Console DTOs are preserved | typed Task contributions -> generic CLI/Web hosts -> external-safe projection | affected process run `5d07ed065a98413da4b77ed8125045ba`; Web/system evidence in FINAL | PASS |
| active-Task gate and cleanup attribution are preserved | application-injected predicate / typed cleanup contribution -> generic host | focused architecture/contract and affected evidence; FINAL | PASS |

The canonical Task schema, status set, record shape, data path and lock path
are unchanged:

```text
buddyswitch/objects/task-sys/tasks/*.json
buddyswitch/local/locks/task-sys/<actor>-<role>.lock
active | completed | canceled
```

`src/buddyswitch/modules/task/private/domain/task_sys.py` is byte-identical to
the former domain owner. `_persist_task` remains the sole Task writer.

## 4. Architecture proof

The accepted candidate has:

- one physical Task root at `src/buddyswitch/modules/task/**`;
- one Task Public surface with exact current cross-component operations;
- zero Task-to-Demand source imports;
- exactly two Demand-to-Task edges, both Task Public;
- one application construction of Task with the Demand resolver;
- one explicit contributed daemon order:
  `demand_triage -> task_goal -> demand_orchestration`;
- one registration-owned mailbox command factory for
  `task_goal.reconcile_task`;
- one Tool, one Goal handler, one CLI command, one Actor Console section and
  one cleanup contribution;
- generic ToolContext, CLI, Web and daemon hosts with no Task-private object or
  retired Task import;
- Task-owned tests co-located under the module and excluded from the runtime
  distribution;
- one public test runner.

The hub parsed all 408 current Python files. Task-private imports outside the
Task root are limited to the sole root-test adapter
`tests/support/task_fixtures.py`; there are no retired Task imports. The
application boundary remains explicit and introduces no plugin discovery,
service locator, DI container, semantic event bus or compatibility layer.

## 5. Replacement and residue proof

S3 closes `R-TASK-001` completely and closes the Task portions of:

```text
R-FND-001
R-FND-002
R-FND-003
R-FND-004
R-FND-006
R-FND-008
R-FND-011
R-FND-012
R-DOC-002
R-DOC-003
```

The retired source and owning-test paths are absent from both the checkout and
installed distribution:

```text
src/buddyswitch/env/domain/task_read.py
src/buddyswitch/env/domain/task_sys.py
src/buddyswitch/env/tools/task_sys/**
src/buddyswitch/env/tool_runtime/task_goal_runtime_client.py
src/buddyswitch/env/tool_runtime/task_goal_runtime_protocol.py
src/buddyswitch/launcher/task_goal_handler.py
tests/integration/task_sys/**
tests/integration/goal_mode/test_task_goal_reconciliation.py
```

Current code and architecture documents point to the new owner. Historical
memos and negative absence assertions may still name retired paths; they are
not live compatibility.

## 6. Verification evidence

Known R1 RED:

```text
command:
./buddyswitch-test focused \
  tests/process/cli/test_env_tool_package_independence.py \
  tests/process/cli/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_private_impl_modules

run:
799f1854ca9b4f37ba55cd394df8932c

result:
3 failed, 5 passed, 14 subtests

owning diagnosis:
generic package/router proofs still invented the retired Task package and
omitted the component-private Tool root
```

The same exact command passed as run
`cc5a797cd76943f9a256a9027b23d435` with 6 tests and 15 subtests. The nearest
Task architecture/contract group passed as
`886a28b515d048fdb9bc2fd367bde294` with 91 tests and 26 subtests.

Affected preservation passed in three runner-owned groups:

```text
classified unit/integration/module-local:
addf01ca26e24149b9f0b7b2e1d99301
337 passed, 307 subtests

process/package:
5d07ed065a98413da4b77ed8125045ba
58 passed, 44 subtests

Browser lazy release + Goal/Demand product flow + clear/resume:
38ad62540de645a6b8c08a1903dc53db
5 passed
```

Frozen FINAL:

```text
command:
./buddyswitch-test full

run:
79c7f25e1c03484d9b600a85bd503712

exit:
0

Unit Python:
434 passed, 1,123 subtests

Unit JavaScript:
147 passed

Integration:
761 passed, 442 subtests

Process:
262 passed, 378 subtests

System:
22 passed

shell syntax:
PASS

diff check:
PASS
```

FINAL ran exactly once against the frozen candidate. The hub reproduced the
complete source/untracked and runtime identities and reused this
identity-valid evidence rather than rerunning the repository-wide suite.

## 7. Runtime identity and operations

```text
activated_at:
2026-07-30T03:01:00.208553Z

source_digest:
8f78328a3fddb2a19fbeba3dd3eff9ddd1384ee76e898b2b5ebbf4da0c1e7d5b

distribution_digest:
f13b885405ec04a0f5085949b69f5d0430d563e3aea45c968af925873f264845

package version:
0.1.0

runtime.verify:
ok=true
```

The installed distribution contains the Task component, excludes its tests
and contains none of the retired Task paths. The final environment has zero
instances, inactive Browser state, no `/private/tmp/bs-test-*` root, no
attributable test/daemon process, no checkout socket or lock and no
deleted-open checkout file.

## 8. Contrary evidence disposition

| Signal | Owning diagnosis | Disposition | Resolved |
|---|---|---|---|
| initial wheel activation `RUNTIME_MISMATCH` | ignored `build/lib` retained deleted Task files | existing build artifacts moved to Trash; clean PEP 517 build/install/activate/verify passed | YES |
| run `2640e495…` collected no tests | module-local root spans runner tiers | expanded to five concrete files; focused group passed | YES |
| run `88446a91…` found three classified defects | two indirect Public edges, overbroad assertion and missing component registration in moved test | owner-correct source/test repairs, reprovision and GREEN `886a28b5…` | YES |
| historical wrong-node run `d5c442…` | invalid test node | retained as non-evidence; correct targets passed | YES |
| command-construction diagnostics | local shell/hash/query mistakes without repository mutation | corrected before evidence; no candidate or environment impact | YES |

No FINAL failure, timeout, flake or cleanup residue occurred. No undeclared
dependency was installed. The only operational finding is that wheel
construction must begin from an empty build tree; the accepted runtime and
FINAL already prove the clean declared path.

## 9. Current documents

Executable truth is reflected in:

```text
docs/arch/task-sys-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/daemon-service-architecture.md
docs/arch/web-interface-call-architecture.md
```

They name the one Task component, acyclic Public boundary, typed
contributions, exact daemon order and absence of central Task branches.

## 10. Acceptance and next boundary

All material Product, Contract, Architecture, Replacement and Operations
proof classes pass. No material check is omitted and no unresolved contrary
signal remains.

S3 is therefore `ACCEPTED`. Both S3 execution packets are consumed and must
not be resumed. This record authorizes only:

```text
checkpoint accepted S3
  -> refresh S4 source/consumer/state/test facts
    -> freeze shared host contracts and lane dependencies
      -> prepare and READY-review lane-sized Goal Packets
```

It does not authorize S4 implementation.
