# S1 Single Package and Runtime Cutover Goal Packet

> Current disposition: STOPPED before C2 and no longer authorized. See
> `S1-REPLAN-REVIEW.md` and `S1-E1-RETURN-REVIEW.md`. The bounded E1 repair
> also stopped; no successor packet is currently authorized.

> Packet state: STOPPED / SUPERSEDED
> Packet ID: `BS-MM-S1-20260728-01`
> Stage: S1
> Master state at preparation: PROPOSED / runtime migration unauthorized

## 1. Copy-paste independent task request

```text
Create and pursue this goal in the independent task:

Replace BuddySwitch's split checkout/copy runtime with one non-editable
installed package built from src/buddyswitch/**, make every production process
execute that one runtime identity, reduce Actor workspaces to selected
Role/Skill/config/private/project projections, preserve every current product
and lifecycle contract, and delete all retired executable roots and path
bootstraps.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only the S1 packet:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-GOAL-PACKET.md

Follow root AGENTS.md and $buddyswitch-testing. Work checkpoint by checkpoint
and keep S1-EXECUTION-STATE.md resumable. Do not begin S2, do not edit master
migration truth, and do not create compatibility/fallback/dual runtime paths.
When S1 implementation and verification finish, return the packet's exact
asynchronous result and stop. I will bring the result back to the coordinating
task for independent acceptance.
```

## 2. Packet identity

```text
Packet ID: BS-MM-S1-20260728-01
Prepared: 2026-07-28, coordinating hub
Worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Branch: fea-tool
Source commit: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
Starting tracked patch:
  7c861a672c53231aea422660f38ae3c2f0114837d67a4f5f84992da866c785ab
Starting index patch:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
Starting untracked paths: 50 coordinating-owned memo/packet files
Starting untracked path-set:
  5953ea022780a5ff21a9a786a9cfd74a9a4da822d0379c33c65875c50008f7b9
Predecessor: S0 ACCEPTED; S1 E0 prerequisite ACCEPTED
```

The tracked patch is accepted E0 source truth, not executor-created dirt. At
start, confirm exact HEAD, tracked/index hashes and untracked path set before
editing. Any mismatch stops the packet.

## 3. Goal and acceptance

Goal:

> Cut every current BuddySwitch runtime and lifecycle consumer directly to one
> installed package and one runtime identity, then remove the checkout/copy
> implementation model completely.

Acceptance:

> Every current BuddySwitch capability executes from one non-editable package
> built from `src/buddyswitch/**`; all BuddySwitch processes report the same
> verified runtime identity; Actor workspaces contain only the exact selected
> projection; current behavior and terminal lifecycle effects pass; every old
> executable root, copied implementation, path bootstrap, dynamic source load
> and stale current guidance is absent.

Consumer path:

```text
explicit setup -> wheel -> installed venv -> activation record
root CLI -> verified installed Python -> package CLI entrypoint
CLI/Web/Daemon/App/Broker/Browser -> package child entrypoints -> current owners
Actor start -> package Role/Skill resources -> exact workspace projection
Tool request -> installed MCP -> installed Broker -> installed owner
root test command -> activated Python -> root runner -> installed package
```

Explicit non-goals:

- no S2 Demand componentization or later module/RoleHost work;
- no product feature, schema or canonical-data migration;
- no general plugin, registry, DI, event bus or multi-version runtime manager;
- no compatibility import aliases, old/new config, fallback reads or copied
  implementation;
- no redesign of CLI, Web, IM, Tool, Daemon, Browser or Actor behavior.

## 4. Required read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and its required references;
3. `2026-07-28-buddyswitch-explicit-modular-monolith-design.md`;
4. `2026-07-28-buddyswitch-modular-monolith-migration-roadmap.md`;
5. `../00-execution-governance.md` and `../00-coordination-hub.md`;
6. `../01-single-package-runtime-cutover.md`;
7. this directory's `README.md`;
8. `00-formal-source-snapshot.md`;
9. `01-package-contract.md` through `06-replacement-and-acceptance.md`;
10. `S1-VERIFICATION-MATRIX.md`;
11. `../decision-log.md` D-002–D-009 and D-020–D-036;
12. `../../2026-07-28-buddyswitch-modular-monolith-readiness-audit/finding-register.md`
    F-029–F-032;
13. `../residue-register.md` R-PKG-001–R-PKG-018 and R-DOC-001;
14. current code/contracts/tests/`docs/arch/**` named by those documents.

Historical HTML/memos are context only. They never override current
executable contracts or the accepted S1 packet.

## 5. Allowed and forbidden scope

```text
OWNER:
  pyproject.toml
  src/buddyswitch/**
  .gitignore
  requirements-test.txt

PUBLIC CONSUMER:
  buddyswitch-codex
  buddyswitch-test

CURRENT SOURCE TO MOVE/DELETE:
  scripts/**
  tools/launcher/**
  tools/__init__.py
  buddyswitch/manifest.toml
  buddyswitch/env-profiles/**
  buddyswitch/skills/**
  framework/contracts/**
  framework/config/**
  framework/schemas/**
  framework/agent-registry.md

PROOF:
  tests/**

CURRENT DOC/GUIDANCE:
  README.md
  AGENTS.md
  docs/arch/**
  Role AGENTS and packaged Skill guidance moved by S1
  CLI/help/error text in allowed source

EXECUTOR RESUME STATE:
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
    01-single-package-runtime-cutover-plan/S1-EXECUTION-STATE.md

HUB-OWNED DIRTY WORK TO PRESERVE, NEVER EDIT OR STAGE:
  every other docs/memo/2026-07-23-* and docs/memo/2026-07-28-* file

FORBIDDEN:
  projects/app/**
  buddyswitch/objects/**
  buddyswitch/local/private/**
  active instance/private/runtime state
  future-stage architecture or implementation
  unrelated repository/configuration files
  push, merge, PR, destructive Git rewrite
```

No unclassified path may change. If a required current consumer lies outside
this table, stop and return the path/reason; do not broaden locally.

Local checkpoint commits are allowed for resumability after a checkpoint is
GREEN. They may contain only S1 implementation/current-doc/proof changes,
including the accepted E0 tracked baseline where a moved file necessarily
absorbs it. Never stage hub-owned memo files; `S1-EXECUTION-STATE.md` remains
uncommitted. Do not push, merge, amend or rewrite history.

## 6. Frozen decisions and protected behavior

Applicable decisions:

```text
D-002–D-009
D-020–D-022
D-025–D-030
D-031–D-036
```

Protected current contracts:

- public CLI commands, JSON success/failure envelopes and exit semantics;
- exact current Roles: `market`, `pm`, `design`, `dev`, `test`;
- Tool IDs, schemas, authority, results and parent/side visibility;
- Actor start/input/interrupt/compact/clear/resume/stop/delete effects;
- Daemon scheduling, restart and recovery effects;
- Web/IM/iMessage worker and Browser lifecycle behavior;
- shared project seed-once/projection/delete safety;
- canonical persisted schemas, identities and data paths;
- cleanup, ambiguity refusal and destructive-path safety.

Canonical data must not move or dual-write. S1 may replace repository-path
inference with explicit locators while preserving the same consumer-observed
data. Discovery of a necessary data migration is an immediate stop.

Runtime provisioning is explicit setup, never launch behavior. The package
source digest covers `pyproject.toml` plus `src/buddyswitch/**` build inputs.
The root test runner is the sole test-only checkout `.py` execution exception;
all production processes are installed-package module entrypoints.

Root shell wrappers resolve only the runtime directory and deterministic
`venv/bin/python`. They never parse activation JSON; the installed activation
owner alone verifies the record.

## 7. Execution sequence

Proceed in this exact order. Update `S1-EXECUTION-STATE.md` after each
checkpoint. Do not merge or declare acceptance at an intermediate checkpoint.

### C1 — package/install/activation contract

Read `01-package-contract.md`.

First RED:

- add the three exact test files from C1 in `S1-VERIFICATION-MATRIX.md`;
- prove current source has no package/build/activation contract;
- the static RED runs in unit; wheel/venv/install/activation REDs run in
  process.

GREEN:

- create one `pyproject.toml`, minimal package roots and activation owner;
- build, install and inspect a real non-editable artifact;
- implement exact setup/activation identity and drift rejection;
- update `.gitignore`, requirements and test support;
- run the complete C1 matrix and clean all build/runtime outputs.

Use `/Users/chen/miniconda3/bin/python` as the source-bound bootstrap
interpreter for the repository runtime in this packet. The production contract
remains `requires-python`, not this machine-specific path.

Stop if package content needs recursive inclusion outside explicit asset
roots, editable/source imports, a second build owner or runtime fallback.

### C2 — direct source and asset move

Read `02-source-and-asset-move-map.md`.

- repeat the 228-path disposition manifest before moving;
- use direct moves into the frozen package targets;
- update imports/resources/tests in the same coherent block;
- retire the two facades exactly as specified;
- run C2 proof from the installed package with source `PYTHONPATH` absent.

Stop on an unmatched source, a live consumer of a planned deletion or a
semantic-owner change. Do not preserve an old import alias.

### C3 — public/process entrypoint cutover

Read `03-process-entrypoint-cutover.md`.

- cut root CLI and every exact child surface to package modules;
- keep root test runner as the one test-only exception;
- remove Broker repo-root/dynamic source loading;
- propagate one immutable runtime identity;
- run the complete process tier as C3 proof.

Stop on a new executable surface not present in the entrypoint allowlist.

After C3, any change to `pyproject.toml` or `src/buddyswitch/**` invalidates the
activation source digest. Rebuild, reinstall and reactivate before invoking
the public test runner; never weaken drift verification for iteration speed.

### C4 — Actor projection

Read `04-actor-workspace-projection.md`.

- remove `repo_root` and implementation copy inputs;
- materialize only the exact S1 Actor allowlist;
- preserve Role/Skill/config/private/auth/shared-project semantics;
- run the exact C4 unit/integration/process/system groups.

Stop if implementation or all/unselected Roles/Skills must enter the Actor
workspace.

### C5 — lifecycle and every consumer

Read `05-lifecycle-and-consumer-proof.md`.

- prove every lifecycle row and terminal failure agreement;
- run all integration and system tests in the C5 matrix;
- perform the isolated real temporary Actor lifecycle;
- record runtime/process/Actor identities and cleanup.

If real-Actor proof is externally blocked, return the exact blocker. Do not
substitute a mock and claim the row accepted.

### C6 — replacement and frozen FINAL

Read `06-replacement-and-acceptance.md`.

- update all active current docs/guidance with executable truth;
- delete every listed old root after all consumers are cut over;
- run and classify exact residue scans;
- rebuild/reinstall/reactivate the frozen candidate;
- rerun any proof invalidated by the final source digest;
- run `./buddyswitch-test full`;
- run final real lifecycle/identity/cleanup/residue evidence.

`full` is authorized only here. If the frozen candidate changes afterward,
rerun affected focused proof and `full`.

## 8. Replacement and residue

Owned residue: all S1 `R-PKG-*`, affected `R-DOC-*` and old Actor copy/path
bootstrap rows in `../residue-register.md`.

Required absence:

```text
tracked scripts/**
tracked tools/launcher/**
tools/__init__.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/**
buddyswitch/skills/**
framework/contracts/**
framework/config/**
framework/schemas/**
framework/agent-registry.md
runtime imports from old top-level roots
source PYTHONPATH or sys.path mutation
checkout .py execution by production processes
spec_from_file_location/dynamic Tool source load
Broker --repo-root source loading
Actor workspace implementation roots
current docs/guidance teaching retired paths
```

Historical memos and exact negative guards may name retired strings. Classify
every match; do not edit history merely to make a search empty.

## 9. Verification authority

Use only:

```bash
./buddyswitch-test focused <exact target...>
./buddyswitch-test full
```

Follow `S1-VERIFICATION-MATRIX.md`. Manual package inspection and real Actor
checks supplement the runner; they do not replace it. Every process-owning
proof records cleanup and leaves no process, PID, socket, lock, temp runtime or
build output.

The executor proposes S1 acceptance. Only the coordinating hub reviews the
final source/diff/distribution, reruns required current proof and changes the
master ledger.

## 10. Stop and return early

Stop without broadening when:

- starting source/diff/untracked identity differs;
- an allowed path already contains unrelated overlapping work;
- a semantic owner or frozen disposition is contradicted;
- another stage's owner/contract is required;
- canonical data or an external protected contract must migrate;
- an old/new compatibility path or runtime coexistence appears necessary;
- installed runtime identity cannot remain singular;
- tests can pass only from checkout imports or copied implementation;
- a direct proof cannot detect the claimed outcome;
- a real lifecycle terminal result contradicts persisted/protocol/consumer
  truth.

Update `S1-EXECUTION-STATE.md`, return evidence and propose `REPLANNING`. Do
not improvise a wider architecture.

## 11. Required asynchronous return

```text
Packet ID: BS-MM-S1-20260728-01
Goal status:
Starting HEAD / tracked patch / index patch / untracked identity:
Final HEAD / local checkpoint commits / exact start-to-final diff:
Completed C1–C6 outcomes:
Created/moved/deleted files and final package tree:
Distribution manifest/version/digest/package root/interpreter:
Focused commands, run IDs and results by checkpoint:
FINAL full run ID/result/duration:
Public CLI and child-process runtime identity evidence:
Actor workspace allowlist and real lifecycle evidence:
Consumer-observed preserved contracts:
Old-root/current-guidance residue scan and classifications:
Cleanup/residual process/PID/socket/lock/temp state:
Proposed residue closures/new findings:
Current docs changed:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed S1 ACCEPTED / REJECTED:
```

Stop after returning this block. Do not begin S2 and do not wait on or contact
the coordinating task; the user will bring the result back.
