# S1 C2–C5 Atomic Installed-Runtime Cutover Goal Packet

> Packet ID: `BS-MM-S1-C2C5-20260728-01`
> Packet state: READY
> Stage: S1 / C2–C5
> Prepared by: coordinating hub
> Source: `S1-C2-C5-SOURCE-SNAPSHOT.md`
> Plan: `S1-C2-C5-IMPLEMENTATION-PLAN.md`

## 1. Copy-paste independent task request

```text
Create and pursue this goal in the independent task:

Atomically move every current BuddySwitch implementation and runtime resource
into the one installed src/buddyswitch package, cut the root launchers and
every child process to verified package-module entrypoints, remove all
BuddySwitch implementation from Actor workspaces, and prove the complete
current lifecycle without changing product semantics. Stop at the C5 return
gate; do not execute C6.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-C2-C5-GOAL-PACKET.md

Follow root AGENTS.md, $buddyswitch-testing and
superpowers:executing-plans. Execute
S1-C2-C5-IMPLEMENTATION-PLAN.md task by task. C2 source movement, C3 process
cutover, C4 code-free Actor projection and C5 lifecycle proof are one atomic
replacement unit: do not stop at or preserve an intermediate path. Do not
edit coordinating migration truth except S1-C2-C5-EXECUTION-STATE.md; do not
run full, begin C6/S2, stage, commit or add compatibility. When the packet
finishes or a stop condition triggers, return its exact result packet and
stop. I will bring the result to the coordinating task for acceptance.
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
46f8cbda03078a0db6352ea5e349558616f86fa56d493fafdb35a6871f5029eb

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
12

non-memo path-set SHA-256:
b1f4e9eaec7c55d6f845269d2a8b2d7df42a913c8d6ed95746a45a8b87f464b2

non-memo length-framed path/content SHA-256:
4bd55023545f2df66c3a0efdfa86f8588f62cde566ecf124eade7b77a7bbd9e0

runtime-source partition:
228 paths / 223 MOVE / 5 DELETE / 0 collision / 0 unmatched

runtime-source sorted-NUL path-set SHA-256:
449257b47b957085b2f2596b6c275606eec0dd007f453cb037e44ed33b389477

runtime-source length-framed path/content SHA-256:
809109763588220b2b74264ed2183d3fa3e9b4e091cdab37adc158d911894239

index:
must remain empty

commit/branch changes:
forbidden
```

At start, independently recompute all identities and record the complete
coordinating-owned `docs/memo/**` identity. Stop on any executable
disagreement. Preserve every coordinating file except the authorized executor
state.

## 3. Goal and acceptance

Acceptance sentence:

> Every current BuddySwitch capability in the C2–C5 candidate executes from
> one installed package built from `src/buddyswitch/**`; every BuddySwitch
> process reports the activated runtime identity; Actor workspaces contain
> only selected projections; all old executable/resource roots are absent;
> the complete current lifecycle remains behaviorally unchanged and clean.

Terminal path:

```text
public action
  -> deterministic activated interpreter
    -> verified package entrypoint
      -> current owner
        -> exact result/state/cleanup
```

Explicit non-goals:

```text
C6 current root/docs guidance and final residue acceptance
./buddyswitch-test full
S2+ component or RoleHost work
product behavior/schema/authority redesign
canonical user-data movement
compatibility, fallback or a second runtime
git stage/commit/branch/merge
```

## 4. Accepted pre-READY evidence

| Evidence class | Identity | Result |
|---|---|---|
| C1 package/runtime preservation | `edc222ac236d4422a5bb9da00e19a26d` | 56 passed, 29 subtests |
| complete affected unit preservation | `874221ab1d224e90b2258e771cd9b597` + `2f3a913a614949029aaafe71b3679d36` | 427 passed, 1129 subtests across non-overlapping groups |
| complete affected integration preservation | `ffc941cb10b443598e8fcf9e2434404a` + `2ed69e58d50a4faf8f1c3a11800159b0` | 756 passed, 440 subtests across non-overlapping groups |
| complete process preservation | `6768ab5bf5284b3987f1022708caa792` | 250 passed, 379 subtests |
| complete system lifecycle preservation | `daa2d57225484b38943edd65da7020b4` | 20 passed |
| stale-fixture RED/GREEN | `284ed5522cf44a009fb1c2a7d5567891` / `e14d3fb26b0e43c992889e2ecca2dd31` | intended RED; 1 passed, 9 subtests GREEN |
| negative standalone-C2 topology | `S1-C2-READY-PREFLIGHT.md` | public/process/Actor contradiction proved |
| representative final topology | `C2C5P-d24c5a85fec6b34a` | 228/228 dispositions, wheel/install/activation PASS, old roots absent, clean |

Preflight fixed the selected mechanism, including the exact
`assets/**/LICENSE*` addition. No architecture choice is delegated.

All test/preflight roots are absent. No BuddySwitch process/resource remains.
`git diff --check` passes.

## 5. Read order

1. root `AGENTS.md`;
2. `$buddyswitch-testing`;
3. `superpowers:executing-plans`;
4. `../01-single-package-runtime-cutover.md`;
5. `02-source-and-asset-move-map.md`;
6. `03-process-entrypoint-cutover.md`;
7. `04-actor-workspace-projection.md`;
8. `05-lifecycle-and-consumer-proof.md`;
9. `S1-C2-C5-SOURCE-SNAPSHOT.md`;
10. `S1-C2-C5-CONSUMER-MANIFEST.md`;
11. `S1-C2-C5-PREFLIGHT.md`;
12. `S1-C2-C5-IMPLEMENTATION-PLAN.md`;
13. this Goal Packet;
14. current executable contracts/tests named by the plan.

`06-replacement-and-acceptance.md` is context for the later C6 owner, not
authorization to execute C6.

## 6. Allowed and forbidden scope

Allowed:

```text
OWNER:
pyproject.toml
exact 228 old source/resource paths and their frozen targets
named process-runtime helper and fourteen new entrypoints

CONSUMER / HOST CONTRACT / COMPOSITION:
buddyswitch-codex
buddyswitch-test
moved package launcher/runtime code and packaged shell/assets

PROOF:
tests/runner.py
tests/support/**
tests/unit/**
tests/integration/**
tests/process/**
tests/system/**

EXECUTOR STATE:
S1-C2-C5-EXECUTION-STATE.md

GENERATED, NEVER STAGED:
.buddyswitch-runtime/**
```

Preserve without editing:

```text
.gitignore
requirements-test.txt
all other docs/memo/**
```

Forbidden:

```text
AGENTS.md
README.md
docs/arch/**
docs/bitter/**
docs/team_diary/**
projects/app/**
canonical state/data
S2+ source/plan
git index/commit/branch/worktree configuration
```

No unclassified file may change.

## 7. Frozen behavior and replacement

Decision IDs:

```text
D-002–D-009
D-020
D-022
D-025–D-030
D-033–D-038
```

Owned residue:

```text
R-PKG-001–R-PKG-015
R-PKG-017–R-PKG-018
F-037
```

F-037 closure may be proposed after proof. Final R-PKG and documentation
closures remain C6 hub authority.

Required replacement:

- exactly 223 sources/resources move and five retire;
- all imports/resources consume the package owner;
- root production launcher and every child use verified module entrypoints;
- Actor workspace implementation copies and repo-root builder input vanish;
- no compatibility alias/fallback/dual path remains;
- new Actor instance attribution is the exact activation identity;
- absent/mismatched attribution on resume fails before mutation;
- canonical data paths and business behavior remain unchanged.

## 8. Execution sequence

Execute only the ten tasks in
`S1-C2-C5-IMPLEMENTATION-PLAN.md`, in order:

1. source/partition/quiescence verification;
2. six cross-boundary REDs;
3. exact source/resource movement and import/resource rewrite;
4. public/child process cutover;
5. code-free Actor projection;
6. clean build/install/activation;
7. exact GREEN and C1 package proof;
8. complete unit/integration proof;
9. complete process/system/public lifecycle proof;
10. residue/cleanup/result return at C5.

Tasks 3–5 are one internal mutation window. No intermediate checkpoint is
accepted, returned or kept runnable through an old path.

## 9. Verification authority

Use only:

```bash
./buddyswitch-test focused <exact targets>
```

The plan names the RED, direct GREEN and broad milestone commands.

Forbidden:

```bash
./buddyswitch-test full
python -m pytest ...
pytest ...
```

`full` belongs only to the later frozen C6 candidate.

Every result records run ID, exact command, count, duration, source identity
and cleanup. Any resource-owning proof must leave no process, PID, socket,
lock or test root.

## 10. Stop and return early

Stop without broadening when:

- source, move partition, consumer or dirty identity differs;
- another production entrypoint/consumer exists outside the frozen manifest;
- a public command, Tool, lifecycle or persisted semantic contract must
  change;
- canonical data requires migration/coexistence;
- compatibility, old import, copied implementation, fallback or second
  runtime seems necessary;
- another stage/current-guidance owner must change to make C2–C5 executable;
- a required proof cannot discriminate the claim;
- unrelated dirty work overlaps scope.

Return the evidence and proposed replan. The stopped packet is permanently
retired; do not locally patch the specification.

## 11. Required asynchronous return

```text
Packet ID: BS-MM-S1-C2C5-20260728-01
Goal status: COMPLETE or STOP CONDITION TRIGGERED

Starting HEAD / tracked patch / index / non-memo identity:
Starting 228-path partition identity:
Exact final diff identity:

Completed task/checkpoint list:
Changed/created/deleted files grouped by OWNER / CONSUMER / PROOF:
Exact move/delete count and unmatched/collision result:

RED commands, run IDs and intended failure reasons:
Direct GREEN commands, run IDs and results:
Unit/integration/process/system commands, run IDs, counts and durations:

Built wheel manifest/digest:
Activation/runtime identity:
Public CLI and every child-process provenance result:
Actor ID/thread/runtime identity and exact workspace allowlist:
Lifecycle terminal-state results:

Old-root/import/path-loader/Actor-copy absence scans:
Cleanup and residual state:
git diff --check / index / branch / commit state:

Proposed F-037 and residue closures:
Omitted checks:
Residual implementation risk:
Stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```

Stop after returning. Wait for the user to bring the result to the
coordinating task.
