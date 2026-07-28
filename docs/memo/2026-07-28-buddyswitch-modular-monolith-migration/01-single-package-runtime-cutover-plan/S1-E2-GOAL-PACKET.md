# S1 E2 Exact Runtime Correspondence Goal Packet

> Packet ID: `BS-MM-S1-E2-20260728-01`
> Packet state: ACCEPTED / CONSUMED — do not execute again
> READY review: `S1-E2-READY-REVIEW.md`
> Stage: S1 / C1 / E2
> Prepared by: coordinating hub
> Source: `S1-E2-SOURCE-SNAPSHOT.md`

## 1. Copy-paste independent task request

```text
Create and pursue this goal in the independent task:

Make BuddySwitch runtime activation prove exact path-and-byte correspondence
between every valid non-test file below src/buddyswitch/** and the installed
package before writing or accepting activation identity; reject every package
source symlink before exclusions, preserve explicit runtime assets, exclude
only co-located tests/cache, and stop after the bounded C1 repair and complete
pre-move preservation proof.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-E2-GOAL-PACKET.md

Follow root AGENTS.md, $buddyswitch-testing and
superpowers:executing-plans. Execute
S1-E2-REPAIR-PLAN.md task by task. Do not edit coordinating-owned migration
truth, begin C2, change Demand, commit, stage or run full. When the packet
finishes or a stop condition triggers, return its exact result and stop. I
will bring the result to the coordinating task for acceptance.
```

## 2. Packet identity

```text
Worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Branch:
fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch SHA-256:
400730f42c705596458f4eaae174017ee7f7606a10b10b1232a507a04421de4e

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
12

non-memo path-set SHA-256:
b1f4e9eaec7c55d6f845269d2a8b2d7df42a913c8d6ed95746a45a8b87f464b2

non-memo path/content manifest SHA-256:
8fba07ee7143c6efa7bd57f75a4fbf578b7c8e69a6588ff6ede390b04f665508

index:
must remain empty

commit/branch changes:
forbidden
```

At start, independently recompute this identity and the complete
coordinating-owned `docs/memo/**` identity. Stop on any non-memo disagreement.
Preserve all coordinating-owned memo files without editing them.

Exact starting hashes for the only six writable files:

```text
f72237fad7e387c60e28c4a77faec7a356a55355aab6291f31c0075253bbed0a
  pyproject.toml
a0ae383707f460500e18794b2cf86e0b5711d9d6f478e7b1dc2ab9f4b2f4cde1
  src/buddyswitch/foundation/process_runtime/activation.py
df69406bf22fcf9cc4967287622cb24d61bc9bf573c39206e3d237c91a7488fe
  tests/support/package_runtime.py
7dda1ebf67af6773091b56d1e4c40da76d21dc89194696db7173932b09d56aca
  tests/unit/architecture/test_package_contract.py
0b7fd18fe0f1a5e537913d3e9e06775b2dbdc4bfee49afeb653ba22f55228c5e
  tests/process/package/test_distribution_install.py
15884c75626654759c8fe7198b71c698d57411c80f9022125718c4f5b6f481a8
  tests/process/package/test_runtime_activation.py
```

## 3. Goal and acceptance

Acceptance sentence:

> Given a non-editable BuddySwitch wheel and its checkout source, activation
> succeeds only when every regular non-test file below
> `src/buddyswitch/**` has exactly one installed package counterpart at the
> same relative path with the same bytes, the installed package has no
> unrecorded counterpart, and the package source contains no symlink.

Consumer-observed terminal truth:

```text
exact correspondence
  -> activate exit 0
  -> one atomic 0600 activation record
  -> verify/status return the same runtime identity

any path/content/symlink disagreement
  -> activate/verify exit 6 and RUNTIME_MISMATCH
  -> no first record or byte-identical existing record
  -> no fallback/source import/partial activation
```

## 4. Pre-READY evidence

### Design and mechanism

```text
record:
S1-E2-PREFLIGHT.md

evidence:
E2P-1c5a001693442adc

probe source:
908e638ba73fdc2a1725674b557ca5ff207ceed69cbf337020c316f3f010907b

canonical semantic result:
1c5a001693442adc57cfd0691ef1ebc4ffcf7202a6cad43fa44b7f20538c0102

result:
11/11 representative positive/adversarial scenarios discriminated

cleanup:
active probe root absent; recovery copy in user Trash; no open handle
```

### Complete pre-mutation preservation

```text
C1:
d2fe4bb7b85f416fb42aacfd6798146e
53 passed, 29 subtests passed

C2 unit:
90678f930b614b91a2c2df0ff66016e8
314 passed, 1035 subtests passed

C2 integration:
a5b0e1edee794816801d996438eb3f98
353 passed, 276 subtests passed

cleanup:
all three run roots absent
```

These runs are cross-task reusable only if the exact executable identity in
this packet matches. A newer failure supersedes them.

## 5. Allowed and forbidden scope

Writable:

```text
pyproject.toml
src/buddyswitch/foundation/process_runtime/activation.py
tests/support/package_runtime.py
tests/unit/architecture/test_package_contract.py
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
```

Read-only dirty work includes:

```text
.gitignore
requirements-test.txt
scripts/runtime_kernel/__init__.py
tests/integration/runtime/test_runless_contract.py
tests/unit/architecture/test_external_control.py
tests/unit/architecture/test_tool_runtime_contract.py
tests/unit/env_tool/test_semantic_contract.py
all docs/memo/**
```

Forbidden:

- every other executable, test, fixture and current architecture file;
- production Demand, Tool, daemon, launcher, Actor, state, Web, Skill or
  lifecycle behavior;
- C2 source/asset movement and old-root deletion;
- compatibility/fallback/editable/source import/`PYTHONPATH`;
- generated build manifest, custom backend, setuptools parser or second
  content owner;
- activation schema, record-field, command or exit-code changes;
- master ledger/decision/finding/residue/READY/acceptance edits;
- commit, stage, branch change and `./buddyswitch-test full`.

No unclassified file may change.

## 6. Frozen design

Read:

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and required references;
3. `../00-execution-governance.md`;
4. `../decision-log.md`, especially D-037;
5. `../01-single-package-runtime-cutover.md`;
6. `01-package-contract.md`;
7. `S1-E1-RETURN-REVIEW.md`;
8. `S1-E2-PREFLIGHT.md`;
9. `S1-E2-SOURCE-SNAPSHOT.md`;
10. `S1-E2-REPAIR-PLAN.md`;
11. current six writable files and their direct callers/tests.

Frozen mechanism:

- `pyproject.toml` owns package selection/data;
- source manifest owns regular non-test source files;
- installed `RECORD` plus actual package-root scan owns installed content;
- exact relative path sets and bytes must agree;
- full source-tree symlink rejection runs before tests/cache filtering;
- full installed-tree symlink rejection runs before cache filtering;
- `pyproject.toml` remains additional build attribution;
- compare at both `activate` and `verify`;
- old independent source scan is removed, not retained as fallback.

## 7. Execution

Execute `S1-E2-REPAIR-PLAN.md` in order:

1. write the exact package/correspondence/symlink RED;
2. run RED before `pyproject.toml` or production changes;
3. remove false docs/projects exclusions;
4. implement the one source/installed correspondence owner;
5. rebuild, force-reinstall and reactivate the one local runtime;
6. run direct GREEN;
7. run complete C1, C2 unit and C2 integration affected groups;
8. audit replacement, scope, identity and cleanup;
9. return and stop.

Use only:

```text
./buddyswitch-test focused <exact targets>
```

Reuse pre-READY preservation evidence rather than rerunning it before the RED
when identity matches. Run all three affected groups after GREEN.

## 8. Stop and loop breaker

Stop immediately on any condition in `S1-E2-REPAIR-PLAN.md`, including:

- need for another owner/backend/parser/manifest;
- an evading package-source symlink;
- legitimate asset/test exclusion contradiction;
- public activation contract change;
- seventh writable file;
- new preservation failure family;
- identity or unrelated dirty-work disagreement.

This is the architecture-reviewed successor after repeated invalidation at the
same boundary. A specification contradiction returns:

```text
ARCHITECTURE_REOPEN_REQUIRED
```

There is no E3 patch-on-patch repair. Do not broaden or improvise.

## 9. Exact asynchronous return

```text
Packet ID:
Goal status:
Starting HEAD / tracked patch / index patch:
Starting non-memo count / path-set / content manifest:
Starting hashes of all six writable files:
Exact final diff and changed files:
New RED run ID / result / intended failure causes:
Direct GREEN run ID / result:
C1 milestone run ID / result:
C2 unit pre-move run ID / result:
C2 integration pre-move run ID / result:
Installed runtime source/distribution/package/interpreter identity:
Correspondence scenarios proved:
Activation failure effects and record immutability proof:
Old independent source-scan removal proof:
F-034 / R-PKG-019 closure proposal:
Cleanup / residual state:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed prerequisite ACCEPTED / REJECTED:
```

Stop after returning. Only the coordinating hub may accept E2, close
F-034/R-PKG-019, accept C1 or authorize C2.
