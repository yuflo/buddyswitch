# S2 Demand Component Pilot Goal Packet

> Packet state: `ACCEPTED / CONSUMED`

This packet completed as part of the candidate accepted in
`S2-ACCEPTANCE.md`. It is retained as execution history and must not be
resumed.

## 1. Copy-paste session request

```text
Create and pursue the following goal in this independent session:

Execute BuddySwitch packet BS-MM-S2-20260729-01: complete the S2 Demand
Component Pilot against frozen source 28ca25d93b84c0165fa4cd6f92744744c1df5d67.
Make Demand one physical module selected once by application composition,
cut every current host and cross-component consumer to typed contributions or
Demand Public, preserve all current Demand/Task/Goal/Actor behavior and
canonical state, delete every old Demand live path, run the packet's focused
and frozen full acceptance, return the exact execution result packet, and
stop. Do not begin S3 or edit master migration truth.

Use only this Stage Goal Packet and its governing repository instructions.
Do not begin another stage. When implementation and verification finish,
return the required execution result packet and stop; do not update the master
migration ledger or declare the stage accepted.
```

## 2. Packet identity

```text
Packet ID: BS-MM-S2-20260729-01
Stage: S2 Demand Component Pilot
Master state: READY
Prepared by: coordinating hub
Prepared date: 2026-07-29
Source commit: 28ca25d93b84c0165fa4cd6f92744744c1df5d67
Tracked patch identity at source: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
Non-ignored untracked identity at source: empty
Execution branch/worktree: current fea-tool worktree; do not switch or rebase
Predecessor acceptance: S1-ACCEPTANCE.md
```

Coordinating preparation docs are expected to be untracked or committed at
handoff. They are read-only to the executor.

## 3. Goal and acceptance

Goal and acceptance sentence are exact in `S2-IMPLEMENTATION-PLAN.md`.

Explicit non-goals:

- S3 Task/Goal migration;
- other component lanes;
- final S5 Tool/Host scanner convergence beyond removing Demand;
- S6 RoleHost;
- Web feature work;
- universal plugin infrastructure;
- compatibility or data migration.

## 4. Pre-READY evidence

```text
Complete affected preservation:
  1ae2966bf66f4616afad03e4e955066a
  92 passed, 65 subtests, clean
Cleanup/CLI preservation:
  298084964b1f463ab94c15f71171dffd
  7 passed, clean
Boundary negative:
  c6fae094fda84117abf9ba27a69916b5
  local module test rejected by current runner, exit 2
Runner positive:
  S2R-etz5nsrl / 6b4a815bb9cf46fd8dc84d315efce9e8
  public wrapper 1 passed, clean
Representative final topology:
  S2P-uyunx4fg
  move/build/install/activate/import and duplicate/invalid rejection PASS
Cleanup correspondence/safety:
  S2C-m_jup0nj
  role/all-data attribution and escape rejection PASS
Source/diff/toolchain:
  S2-SOURCE-SNAPSHOT.md
Cleanup:
  all fixture and run roots absent; zero current instances
Residual private risk:
  exact implementation/import/injection work only
```

## 5. Read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and required references;
3. `docs/memo/2026-07-28-buddyswitch-explicit-modular-monolith-design.md`;
4. roadmap, coordination hub and execution governance;
5. `02-demand-component-pilot.md`;
6. every file in this plan directory in README order;
7. applicable decisions and residue rows;
8. current Demand/Daemon/Task architecture and executable tests.

## 6. Allowed and forbidden scope

Allowed classes and exact roots are the scope ledger in
`S2-IMPLEMENTATION-PLAN.md`. No unclassified file may change.

Shared/integration-owner surfaces:

- application composition/build and entrypoints;
- Host registration types and registries;
- `pyproject.toml`;
- `tests/runner.py`;
- root architecture/package/process/system tests;
- current `docs/arch/**`.

The packet grants the executor bounded write authority only for the exact
classified S2 outcome. It does not grant master ledger/decision/residue status
authority.

Unrelated dirty work: none at the frozen source. Stop if new unrelated work
overlaps.

## 7. Frozen behavior and decisions

Use sections 5–6 of the implementation plan. No internal old import is
protected. External CLI/Tool/state/Actor/Skill behavior is protected.

## 8. Execution sequence

Execute Tasks 1–7 in order. Checkpoint after:

1. source identity plus exact REDs;
2. typed composition GREEN;
3. owner/Public movement GREEN;
4. Tool/CLI/Daemon cutover GREEN;
5. Skill/package/runner/cleanup GREEN;
6. replacement/current-doc GREEN;
7. frozen full candidate.

At each checkpoint report source/diff identity, exact files, run IDs, cleanup,
residue and the next action. Do not commit a partially runnable old/new
Demand coexistence checkpoint. Coherent local commits are allowed only after
one live Demand path exists at that checkpoint.

## 9. Residue and replacement

Owned:

- `R-DEMAND-001`;
- Demand portion of `R-FND-001/002/003/006/008/011/012`;
- Demand portion of `R-ROLE-004`;
- Demand portion of `R-DOC-002/003`.

Propose closures only. The hub closes them.

Absence must prove:

- every old owner/adapter/Skill/owning-test path is gone;
- no compatibility import, alias, scanner registration or fallback exists;
- no production file outside the Demand module imports Demand private;
- generic foundation/hosts do not import Demand;
- application has one module-level Demand selection;
- one Tool, two handlers, two Skill exports and one state writer exist.

## 10. Verification

Use only:

```bash
./buddyswitch-test focused <exact targets>
./buddyswitch-test full
```

`full` is authorized only after the S2 diff and installed runtime are frozen.
Record source identity, activation identity, every run ID/result/duration and
cleanup. Manual scans supplement the automated proof.

## 11. Stop and return early

Use the implementation plan stop conditions plus the standard Goal Packet
template. Do not create a repair packet. A stopped packet is permanently
retired and returned to the hub.

## 12. Checkpoint update

```text
Packet / stage / checkpoint:
Source/diff/activation identity:
Completed outcome:
Evidence and run IDs:
Files changed/moved/deleted:
Proposed residue changes:
Current risk:
Next exact action:
Stop/replan condition:
```

## 13. Final asynchronous return

```text
Packet ID and stage:
Starting source and exact final diff:
Final activation identity:
Completed checkpoints:
Changed/created/deleted files:
Focused/final commands, run IDs, results and duration:
Consumer-observed CLI/Tool/Daemon/Actor result:
Canonical state path/schema/write-path proof:
Runtime/process/Actor identities:
Cleanup/residual state:
Proposed residue closures/new residue:
Current docs changed:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```

Stop after returning this packet. Wait for the user to bring the result to the
coordinating session.
