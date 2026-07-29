# S1 C6 Current-Guidance, Residue and Final-Acceptance Goal Packet

> Packet ID: `BS-MM-S1-C6-20260729-01`
> Packet state: READY
> Stage: S1 / C6
> Prepared by: coordinating hub
> Source: `S1-C6-SOURCE-SNAPSHOT.md`
> Scope: `S1-C6-SCOPE-MANIFEST.md`
> Plan: `S1-C6-IMPLEMENTATION-PLAN.md`

## 1. Copy-paste independent task request

```text
Create and pursue this goal in the independent task:

Finish BuddySwitch S1/C6 by replacing every remaining stale current-guidance
path with the exact installed-package owner, adding the one specified
architecture guard, proving final residue classification, and running the
single frozen repository-wide acceptance gate. Preserve the accepted C1–C5
runtime exactly; do not begin S2.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-C6-GOAL-PACKET.md

Follow root AGENTS.md, $buddyswitch-testing and
superpowers:executing-plans. Execute S1-C6-IMPLEMENTATION-PLAN.md task by
task. Modify only the six named non-memo files and
S1-C6-EXECUTION-STATE.md. Do not modify src/**, runtime behavior, product
semantics, any other test/doc/memo, the git index, commits, branches or
remote. Run full only after the candidate is frozen and exactly as authorized.
On completion or any stop condition, return the exact C6 result packet and
stop. Do not accept S1 or begin S2; I will bring the result to the
coordinating task for acceptance.
```

## 2. Packet identity

```text
Worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Branch:
fea-tool

Upstream:
origin/fea-tool

HEAD:
68e1272eb4dad276c8491f642006bbb24218c3f4

HEAD tree:
8d01c3cf57d25c4e5472eb58140a23c9efe780c4

ahead / behind:
0 / 0

frozen non-memo tracked patch:
empty

index patch:
empty

frozen non-memo untracked:
empty

coordinating memo additions/updates:
packet preparation only; preserve all except S1-C6-EXECUTION-STATE.md

commit/branch/remote changes:
forbidden
```

At start, independently recompute the identity. Record all coordinating memo
paths. Stop if any non-memo change exists before C6 begins, if HEAD/tree
differs, or if the index is non-empty.

## 3. Goal and acceptance

Goal:

> Make the accepted installed-package runtime the only truth taught by current
> guidance, enforce that topology at the existing architecture boundary, and
> prove S1 as one clean frozen candidate.

Acceptance sentence:

> BuddySwitch has one current installed-package runtime truth; all active
> guidance names only current owners; every remaining old term is an exact
> negative guard, historical memo or valid unrelated text; the complete
> repository passes its frozen public test gate and leaves no owned resource.

Consumer path:

```text
developer/Actor reads current guidance
  -> exact src/buddyswitch source owner or public installed-runtime interface
    -> architecture test rejects retired path
      -> public full gate proves repository/runtime consumers
```

Explicit non-goals:

```text
any src/**, package, runtime, product or persisted-state change
Role/Skill/CLI/help redesign
S2 Demand component work
S6 RoleHost future path
new documentation framework/linter/generator
compatibility/fallback/second runtime
global deletion of historical or negative old-path text
stage/commit/push/merge/PR
```

## 4. Accepted pre-READY evidence

| Evidence class | Identity | Result |
|---|---|---|
| predecessor runtime cutover | `S1-C2-C5-ACCEPTANCE.md` | C2–C5 accepted; one installed runtime and code-free Actor |
| frozen source | `S1-C6-68e1272-20260729` | HEAD/upstream clean, exact tree, no non-memo patch |
| focused preservation | `978f3133b7dc4a689527ebc0e4262187` | 29 passed, 59 subtests, clean |
| runtime correspondence | source `0240a6d...`, distribution `02344c...` | `runtime.verify ok:true` |
| current-guidance inventory | `C6P-68e1272-20260729` | exact 19 stale occurrences in five files |
| Role/Skill/source inventory | `C6P-68e1272-20260729` | zero retired live-path match |
| old physical roots | `C6P-68e1272-20260729` | zero file/symlink |
| selected enforcement | preflight alternative C | existing package contract, no new framework |

Preflight proves every replacement target exists and classifies every known
remaining active match. No architecture choice is delegated.

## 5. Required read order

1. root `AGENTS.md`;
2. `$buddyswitch-testing`;
3. `superpowers:executing-plans`;
4. `../01-single-package-runtime-cutover.md`;
5. `06-replacement-and-acceptance.md`;
6. `S1-C2-C5-ACCEPTANCE.md`;
7. `S1-C6-SOURCE-SNAPSHOT.md`;
8. `S1-C6-SCOPE-MANIFEST.md`;
9. `S1-C6-PREFLIGHT.md`;
10. `S1-C6-IMPLEMENTATION-PLAN.md`;
11. this Goal Packet;
12. the exact writable files and tests named by the plan.

Other migration memos are historical/context only and do not authorize work.

## 6. Allowed and forbidden scope

Allowed PROOF:

```text
tests/unit/architecture/test_package_contract.py
```

Allowed CURRENT DOC:

```text
README.md
AGENTS.md
docs/arch/daemon-service-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/task-sys-architecture.md
```

Allowed EXECUTOR STATE:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  01-single-package-runtime-cutover-plan/S1-C6-EXECUTION-STATE.md
```

Forbidden:

```text
src/**
pyproject.toml
buddyswitch-codex
buddyswitch-test
docs/arch/web-interface-call-architecture.md
all Role AGENTS and Skills
all other tests
all other migration memos
projects/app/**
runtime/canonical/private user state
.buddyswitch-runtime mutation or reinstall
git index/commit/branch/worktree/remote
```

Generated test roots are runner-owned and must be cleaned. No unclassified
file may change.

## 7. Frozen decisions and behavior

Decision IDs:

```text
D-002–D-009
D-020
D-022
D-025–D-038
```

Protected current contracts:

```text
public launcher and CLI/help behavior
installed distribution/source/runtime identity
Actor projection and lifecycle
all product schemas, authority and persisted effects
canonical data paths
Role/Skill selection and content
```

C6 preserves success, failure, authority, persistence, restart/recovery and
cleanup behavior exactly. Only current path guidance and its architecture
proof change.

## 8. Execution sequence

Execute only the seven tasks in `S1-C6-IMPLEMENTATION-PLAN.md`, in order:

1. verify frozen source and baseline;
2. add exact structural RED;
3. replace five current-guidance documents;
4. run direct and affected GREEN;
5. freeze and prove residue/runtime identity;
6. run one `./buddyswitch-test full`;
7. prove final cleanup and return.

Do not stop between test RED and document GREEN except on a packet stop
condition. Do not change the candidate after the pre-FINAL freeze.

## 9. Residue and replacement

Owned:

```text
R-PKG-016 current root/architecture guidance portion
R-DOC-001
```

Replacement is exactly the eight path mappings in
`S1-C6-SCOPE-MANIFEST.md`. C6 may propose both rows CLOSED after proof.

R-DOC-004 remains assigned to S6. Historical memo terms and negative absence
guards remain intentional.

## 10. Verification authority

Use only:

```bash
./buddyswitch-test focused <exact targets>
./buddyswitch-test full
```

Exact focused commands are in the implementation plan. Direct pytest, a
second runner and alternate broad groups are forbidden.

The active-guidance final scan is:

```bash
rg -n \
  '(scripts/env/|scripts/runtime_kernel/|tools/launcher/|framework/contracts/|buddyswitch/manifest\.toml|buddyswitch/env-profiles/|env_legacy_store|sys\.path\.insert|spec_from_file_location|--repo-root|PYTHONPATH)' \
  README.md AGENTS.md docs/arch \
  src/buddyswitch/launcher/assets/roles \
  src/buddyswitch/skills
```

Expected result: exit 1 and no output.

The production-loader scan is:

```bash
rg -n \
  '(scripts/env/|scripts/runtime_kernel/|tools/launcher/|framework/contracts/|buddyswitch/manifest\.toml|buddyswitch/env-profiles/|env_legacy_store|sys\.path\.insert|spec_from_file_location|--repo-root|PYTHONPATH)' \
  src/buddyswitch
```

Expected result: exit 1 and no output.

Old physical roots:

```text
scripts
tools
framework
buddyswitch
```

Each may remain as an empty directory in the worktree, but must contain zero
file or symlink and is not tracked as a runtime root.

`full` is authorized once only after Task 5 freezes the candidate. Any final
failure stops the packet; do not patch executable code or broaden scope.

## 11. Stop and return early

Stop without local redesign when:

- HEAD/tree/non-memo/index identity differs at entry;
- the RED does not report the exact 19 occurrences and five-file path set;
- another current guidance file contains a retired live path;
- a required replacement source path is missing or ambiguous;
- any `src/**`, runtime, public contract, product semantic or persisted state
  change appears necessary;
- Role/Skill/CLI/help content must change;
- another test or document must change;
- compatibility, fallback, alias or second runtime seems necessary;
- runtime verification digest changes;
- the frozen `full` run fails or leaks a resource;
- unrelated work overlaps exact scope.

Return evidence and a replan proposal. Do not repair the packet locally. This
packet is consumed when it returns, complete or stopped.

## 12. Required asynchronous return

```text
Packet ID: BS-MM-S1-C6-20260729-01
Goal status: COMPLETE or STOP CONDITION TRIGGERED

Starting HEAD / tree / branch / upstream:
Starting non-memo patch / index / untracked identity:
Starting coordinating memo path identity:
Exact final diff and changed files by PROOF / CURRENT DOC / EXECUTOR STATE:

C6.1 baseline command, run ID, result and cleanup:
C6.2 RED command, run ID, exact 19-occurrence result:
C6.3 exact current-guidance replacements:
C6.4 direct and affected GREEN commands, run IDs, counts, durations:
C6.5 frozen candidate identity, residue scans and runtime.verify:
C6.6 full command, run ID, phase counts/durations and cleanup:
C6.7 final scan, git diff --check and resource cleanup:

Current-guidance zero-match result:
Required-current-path existence result:
Old-root file/symlink absence result:
Production-loader absence result:
Repository-wide remaining-match classification:

Runtime source/distribution/package identity:
Reused C2–C5 Actor/process evidence identity:
Index / HEAD / branch / commit / push state:

Proposed R-PKG-016 and R-DOC-001 closure:
R-DOC-004 preserved-open confirmation:
Omitted checks:
Residual risk:
Stop/replan discoveries:
Proposed S1 ACCEPTED / REJECTED:
```

Stop after returning. Wait for the user to bring the result to the
coordinating task. Do not poll, commit, accept S1 or begin S2.
