# S1 Single Package and Runtime Cutover Acceptance

> Decision: ACCEPTED
> Final gate: C6
> Packet: `BS-MM-S1-C6-20260729-01`
> Authority: coordinating hub
> Acceptance date: 2026-07-29
> Next stage: S2 preparation only

## 1. Accepted outcome

The S1 charter acceptance sentence is true:

> Every current BuddySwitch capability executes from one installed package
> built from `src/buddyswitch/**`; every BuddySwitch process reports one
> runtime identity; Actor workspaces contain only selected projections; old
> executable roots, copied implementation and path-surgery bootstraps are
> absent.

The accepted current path is:

```text
root public interface
  -> deterministic activated interpreter
    -> verified installed buddyswitch package entrypoint
      -> current owner
        -> exact product result/state/cleanup
```

Current guidance now teaches that path and the exact package-source owners.
No old executable, fallback, copied implementation or live stale guidance
remains.

## 2. Source and candidate identity

The hub reproduced the executor return before changing this acceptance record:

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch / upstream:
fea-tool / origin/fea-tool

HEAD:
68e1272eb4dad276c8491f642006bbb24218c3f4

HEAD tree:
8d01c3cf57d25c4e5472eb58140a23c9efe780c4

ahead / behind:
0 / 0

frozen non-memo binary patch SHA-256:
83e56e317a37a610dc5b998205b7d568a69775a4aeac568b72efd24de76aaa96

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The exact C6 non-memo changes are:

```text
PROOF:
tests/unit/architecture/test_package_contract.py

CURRENT DOC:
README.md
AGENTS.md
docs/arch/daemon-service-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/task-sys-architecture.md
```

The returned file hashes and executor-state hash reproduce exactly. Every
coordinating C6 memo other than executor state also retained its pre-handoff
hash. No `src/**`, package declaration, launcher, Role, Skill, product test,
state path or unrelated file changed.

## 3. Product and contract proof

S1 is a structural replacement with preserved product semantics. Its
consumer-observed proof is cumulative:

| Claim | Consumer path | Evidence | Result |
|---|---|---|---|
| public and child processes use one installed runtime | CLI/Host -> activated package entrypoint -> current owner | `S1-C2-C5-ACCEPTANCE.md`; FINAL Process/System | PASS |
| Actor workspace is code-free and attributable | start -> Actor builder -> selected projection + runtime identity | Actor `act-pm-dcbbc3e521a8`; thread `thread-act-pm-dcbbc3e521a8`; FINAL System | PASS |
| lifecycle behavior is preserved | roles/start/input/status/clear/resume/stop/delete -> current owners -> terminal result | C2–C5 lifecycle evidence; FINAL Process/System | PASS |
| Tool and product consumers are preserved | MCP/Broker -> env.tool -> product owner | C2–C5 direct/Integration evidence; FINAL Integration | PASS |
| current guidance resolves to current owners | developer/Actor reads current guidance -> package source/public interface | C6 exact RED/GREEN and hub review | PASS |
| failure and cleanup remain attributable | owner/process failure -> protocol/status -> cleanup | C2–C5 operations evidence; FINAL supervisor cleanup | PASS |

No success, failure, authority, persistence, restart/recovery or terminal
product contract changed in C6. The runtime identity still verifies:

```text
kind:
runtime.verify

ok:
true

source_digest:
0240a6d6897a96fc2538f8b883eee4a48f5830c2deb9928e4d9ccaf44809445f

distribution_digest:
02344c6d8e7edd0489cf02f69a28c991fc7364d833f1c1c72f04348a2505f0d7

package_version:
0.1.0
```

## 4. Architecture proof

The accepted topology has:

- one Python implementation/runtime source root: `src/buddyswitch/**`;
- one package/build declaration: `pyproject.toml`;
- one non-editable installed runtime and atomic activation identity;
- thin root public wrappers with no source import path;
- package-module child-process entrypoints;
- explicit runtime/state/project locators;
- code-free Actor workspaces with selected Role/Skill/config/private/project
  projections;
- no top-level compatibility alias, checkout loader, source `PYTHONPATH`,
  `sys.path` mutation or `--repo-root` runtime loading;
- root cross-boundary tests using the one public test runner.

C6 adds one structural assertion to the existing package architecture
contract. It scans root/current architecture, Role AGENTS and packaged Skills
for retired live-path tokens and requires the exact current owner strings. It
does not introduce a linter, generated-doc pipeline, scanner framework,
second runner or policy owner.

## 5. Replacement and residue proof

All S1 package/runtime residue is closed:

| Residue | Accepted closure |
|---|---|
| R-PKG-001–R-PKG-015 | C2–C5 installed-package replacement, consumer cutover and old-root absence |
| R-PKG-016 | C6 current README/AGENTS/docs replacement plus structural absence guard |
| R-PKG-017–R-PKG-018 | C2–C5 activated interpreter/schema/test-support replacement |
| R-PKG-019 | E2 exact source/install path-and-byte correspondence |
| R-DOC-001 | C6 `docs/arch` package-path replacement and zero active-guidance match |

Final scans prove:

```text
active current-guidance retired matches:
0

production-loader retired matches:
0

old scripts/tools/framework/buddyswitch files or symlinks:
0

forbidden live repository-wide residue:
0
```

Remaining old terms are classified as:

- historical migration memos;
- exact negative absence guards;
- valid test/runner environment isolation.

R-DOC-004 remains assigned to S6. The root manifest and Role paths are correct
for the current S1 package topology; S6 later replaces that current topology
with RoleHost. This future owner does not represent stale or parallel S1
guidance.

## 6. Current-document proof

C6 changed:

- root `README.md`: public diagnostics and exact package-source owners;
- root `AGENTS.md`: current package manifest and Role bootstrap paths;
- Daemon architecture: current instance composition-root path;
- Demand architecture: current domain and repository paths;
- Task architecture: current domain and Task–Goal adapter paths.

`docs/arch/web-interface-call-architecture.md`, packaged Role AGENTS, packaged
Skills and CLI/help/error text were already current and remained unchanged.
Historical memos intentionally preserve prior paths and failed packet history.

## 7. Verification evidence

### C6 discriminating proof

```text
RED:
2f4f4f766f44447996389f0366e5f615
1 expected failure
19 exact stale occurrences in five authorized current documents

direct GREEN:
33269f34699a47d4a3c68bc9c362f6e7
1 passed

affected GREEN/IMPACT:
dae67375da724bef8e4bba9a4d172505
66 passed, 345 subtests
```

### Frozen FINAL

```text
command:
./buddyswitch-test full

run ID:
af8cfbbe53ee4710894483c2fcb18350

Unit:
423 passed, 1125 subtests

Unit JavaScript:
147 passed

Integration:
757 passed, 438 subtests

Process:
261 passed, 375 subtests

System:
21 passed

shell syntax:
PASS

diff check:
PASS

cleanup:
PASS
```

The executor changed no non-memo candidate file after FINAL. The hub
reproduced the same frozen patch and reused FINAL under the BuddySwitch
evidence contract. Reviewer identity alone does not invalidate source-bound
evidence.

The hub additionally ran the exact new structural proof against the unchanged
candidate:

```text
run ID:
dde42ea2b544495fbef9f18d40ae8f86

result:
1 passed in 0.01s

runner:
passed in 0.13s

cleanup:
clean
```

`git diff --check`, final runtime verification, active-guidance absence,
production-loader absence, old-root absence and resource cleanup all pass on
the accepted identity.

## 8. Operations and cleanup

At hub acceptance:

- no worktree-owned BuddySwitch or `bs-test` process remains;
- no test run root remains;
- no packet-owned socket, PID, lock, instance or temporary build root remains;
- the index is empty;
- HEAD, branch, upstream and remote are unchanged.

The installed interpreter contains 93 ignored cache/bytecode entries generated
by normal module execution. They are below the ignored
`.buddyswitch-runtime/**` installation, excluded from runtime source/
distribution identity and are not a process/socket/lock/temp or tracked
candidate residue. C6 correctly did not mutate the installed runtime to remove
them.

## 9. Omitted checks and residual risk

A separate manual Actor lifecycle was not repeated in C6. The exact C2–C5
Actor/process evidence remained identity-valid, while C6 FINAL reran the
complete Process and System tiers. Repeating the manual lifecycle would add no
missing claim.

No alternate runner or direct pytest command was used.

No known S1 implementation, semantic, provenance, guidance or cleanup risk
remains. Component/foundation/Role modularization remains explicitly owned by
S2–S6 and is not S1 residue.

## 10. Final acceptance review

- [x] Product proof agrees with persisted and consumer-visible effects.
- [x] Runtime/process contract and identity are exact.
- [x] One implementation/runtime owner remains.
- [x] Actor projection is code-free.
- [x] All S1 old executable/current-guidance residue is absent.
- [x] Current docs match executable truth.
- [x] FINAL passed on the frozen candidate.
- [x] Operations and cleanup are clean.
- [x] No unrelated work was changed, staged or published.
- [x] S1 stands without S2 repairing its runtime truth.

## 11. Transition decision

```text
BS-MM-S1-C6-20260729-01:
accepted and consumed

C6:
ACCEPTED

S1:
ACCEPTED

R-PKG-016:
CLOSED

R-DOC-001:
CLOSED

S2:
PROPOSED — preparation unlocked, no Goal Packet authorized
```

S1 acceptance unlocks source refresh, design validation and READY preparation
for S2 Demand. It does not authorize S2 implementation in this acceptance
step.
