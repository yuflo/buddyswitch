# Goal Packet — BuddySwitch Confirmed Bug Repair

```text
Packet ID: BS-BUGFIX-CONFIRMED-R1-20260814-01
Status: READY FOR INDEPENDENT EXECUTION
Repository: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Branch: fea-tool
Prepared from HEAD: 4522854
```

## 1. Goal to create in the independent session

Create and pursue this goal:

> Repair confirmed BuddySwitch defects F-01, F-03, F-06, F-08 and F-09 at
> their semantic owners, prove the five frozen acceptance contracts through the
> public BuddySwitch test/runtime path, remove the unsafe Actor-ID-to-Role
> parsing model completely, and return an evidence-complete result packet
> without staging, committing or pushing.

Do not create a broader architecture-migration goal. This is one coherent bug
repair goal with three implementation/provisioning cohorts and one final
repository acceptance candidate.

## 2. Required read order

Read completely before editing:

1. repository root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and the references it routes to;
3. `docs/memo/2026-08-14-buddyswitch-confirmed-bug-repair-plan.md`;
4. this Goal Packet;
5. current source, tests and runtime commands implicated by the plan.

Repository facts outrank this packet's path list and implementation sketches.
The acceptance contracts, protected boundaries and proof obligations are
authoritative; paths and candidate test targets are discovery starting points.

## 3. Expected entry identity

The coordinating session prepared the packet from:

```text
HEAD: 4522854 (docs: record real web actor experience audit)
branch: fea-tool
upstream: origin/fea-tool at 4010434
branch relation at preparation: ahead by two documentation commits
activated runtime version: 0.1.0
activated source digest: 1b448cb325b59287913d2e2c52efa4303fe277c9669f19a3c3a623e67cc23921
activated distribution digest: 85ff440cd64eeb8a895af655a7e9b2372856df8fa03741b0534f24bb9887ce7f
```

The following coordinating-owned untracked files are expected and must be
preserved:

```text
docs/memo/2026-08-14-buddyswitch-confirmed-bug-repair-plan.md
docs/memo/2026-08-14-buddyswitch-confirmed-bug-repair-goal-packet.md
```

Record actual HEAD, tracked diff, index, non-ignored untracked manifest,
runtime identity and attributable resource baseline at entry. A difference from
the preparation identity is not automatically fatal: classify it, preserve
unrelated work, and continue when the authorized repair remains partitionable.
Do not reset, clean, stash or rewrite user/coordinating work.

## 4. Frozen result boundary

### F-01 — Actor Identity Profile is the only Actor-to-Role owner

- A Role ID containing hyphens remains valid.
- Task/Demand public Actor-filtered reads return canonical durable records for
  that Actor.
- Communication and Track role cleanup attribute records to the full Role.
- Missing/invalid canonical identity fails safely; no shortened Role is guessed.
- All live Actor-ID reverse parsers are removed, including fallback variants.
- Durable reads must not become dependent on a live Host Instance.

### F-03 — A matched, validly ignored scheduled trigger is delivered

- unmatched remains failed with the no-handler diagnostic;
- matched handler failure remains failed with the real error;
- matched `ignored` becomes schedule `delivered`, retains its ignored dispatch
  result, has no false error, and is not swept again;
- current schedule-generation protection remains intact.

### F-06 — Lifecycle language reflects operation phase

- active/queued operations remain progressive;
- successful terminal operations use completed verbs;
- failed operations retain operation identity and real failure;
- clear-thread result suffixes remain intact.

### F-08 — A stale Actor Console rejection cannot overwrite delete success

- an earlier console request rejected after deletion/selection invalidation
  cannot change the current message, error or selection;
- a failure still owned by the current selection/request remains visible;
- repair request ownership generically at the current owner, not by suppressing
  FileNotFound or adding a delete-only exception.

If the exact deferred-request RED disproves this root cause, stop before editing
F-08 source and return the contrary evidence for replanning.

### F-09 — Ctrl-C is a normal Web CLI shutdown

- the ready JSON output remains singular;
- SIGINT exits successfully without traceback or KeyboardInterrupt text;
- Web/process/port/daemon cleanup remains exact;
- ordinary non-interrupt child exit codes still propagate.

Catch only the scoped parent wait interrupt; do not swallow `BaseException`
globally.

## 5. Explicitly deferred and forbidden

Do not repair, redesign or opportunistically absorb:

```text
F-02 accepted-message/Demand/Task progress-state design
F-04 activity feedback information architecture
F-05 token accounting, latency or execution-efficiency product behavior
F-07 stopped/offline/health presentation or duplicated action guidance
```

Also forbidden:

- changing Role-ID validity or Actor-ID format;
- compatibility parsers, dual reads/writes, migration layers or fallbacks;
- speculative registries, buses, retry engines, request managers, static
  analyzers or test frameworks;
- weakening unrelated failure, confirmation, cleanup or malformed-input rules;
- broad cleanup, formatting or historical architecture edits;
- any stage, commit, push, merge, rebase, branch or destructive Git operation.

## 6. Executor authority

Within the frozen result boundary, the executor owns the shortest current
owner-correct repair. In particular, the executor may:

- correct stale filenames, symbols, test class names and nodeids from repository
  facts without requesting a packet rewrite;
- add or relocate narrow regression tests at the nearest meaningful boundary;
- change an adjacent source/test file when dependency tracing proves it is part
  of the same semantic owner or consumer path;
- omit a hypothesized file when current tracing proves no edit is required;
- batch compatible focused targets and reuse source-valid evidence;
- resolve ordinary local implementation ambiguity without coordinating review.

Report these corrections in the return packet. Stop only when they change
product meaning, cross a protected/external contract, require compatibility or
state migration, overlap inseparable unrelated work, or invalidate a frozen
acceptance contract.

## 7. Execution and efficient proof sequence

Follow the detailed implementation plan. The required order is:

1. Freeze and classify entry state.
2. While product source is unchanged, add and run direct RED proof for every
   F-01/F-03/F-06/F-08/F-09 behavior boundary named in the plan. Do not force
   unrelated assertions into one test merely to minimize the test count.
3. Repair the F-01 Identity cohort completely.
4. Provision/install/activate/verify the changed worktree once, then run F-01
   exact and directly affected GREEN evidence.
5. Repair the F-03 Daemon cohort completely.
6. Provision/install/activate/verify once, then run F-03 exact and directly
   affected GREEN evidence.
7. Repair the F-06/F-08/F-09 Web/CLI cohort completely.
8. Provision/install/activate/verify once, then run its exact and directly
   affected GREEN evidence.
9. Perform replacement/residue review and review-driven fixes. If executable
   source changes, repeat the runtime gate and only the affected evidence.
10. Freeze one final candidate and run one `./buddyswitch-test full` for that
    candidate.
11. Audit cleanup and return the result packet. Do not perform Git publication.

Only these public test entries are allowed:

```bash
./buddyswitch-test focused <validated-file-or-nodeid>...
./buddyswitch-test full
```

Do not run broad tiers during development. Do not rerun unchanged commands just
because the session, actor or reviewer changed. A FINAL failure is evidence, not
permission for a blind retry: diagnose, repair with exact/affected proof,
reprovision if source changed, freeze a new candidate, then run that candidate's
single FINAL.

Every executable source mutation must cross the repository's established
non-editable distribution provision/activate/verify gate before the next public
test-runner command. Discover the current commands from repository-owned runtime
guidance; do not invent a second workflow.

## 8. Review obligations

Before FINAL, inspect the complete candidate for:

- copied or reconstructed Actor-to-Role rules;
- fallback parsing or live remnants of the retired model;
- incorrect dependency direction from Foundation to product modules;
- collapsing unmatched, failed and ignored Daemon outcomes;
- stale-request handling that suppresses current errors;
- lifecycle copy fixed at the wrong backend owner;
- global interrupt suppression or weakened process cleanup;
- unrelated edits, assertion weakening or speculative abstractions.

A bounded residue scan supplements behavioral proof; it does not replace it.
Review comments that require source edits invalidate the preceding installed
runtime identity until reprovisioned.

## 9. Return packet

Return one self-contained result with:

1. Packet ID and proposed disposition: `ACCEPTED`, `REJECTED`, or
   `REPLANNING REQUIRED`.
2. Starting and final HEAD/branch/upstream, tracked patch digest, index state,
   untracked manifest, changed-file list and `git diff --check` result.
3. The implementation selected for each F-number and why it is the semantic
   owner fix.
4. Every valid RED, exact GREEN, affected proof and FINAL command/run identity,
   result and duration; list invalid targets or contrary signals separately.
5. Every provision/activation/verify identity and its correspondence to source.
6. Product, contract, architecture, replacement and operations acceptance
   evidence mapped to the frozen contracts.
7. Cleanup proof for attributable process, port, socket, lock and test roots,
   with pre-existing unrelated resources distinguished.
8. Omitted checks, residual risk and any executor-corrected stale assumptions.
9. Exact statement that no stage, commit, push or other forbidden Git operation
   occurred.

Do not claim acceptance if any frozen contract lacks direct evidence, runtime
identity is stale, a replacement parser remains, terminal observations
contradict each other, or attributable resource residue remains.

## 10. Replanning conditions

Return promptly with grounded evidence when:

- the canonical Identity Profile cannot support the durable-read/cleanup
  contract without data migration or a new protected interface;
- F-08's required RED disproves the traced ownership gap;
- the repair requires product decisions from F-02/F-04/F-05/F-07;
- a real required owner cannot be reached within the authorized semantic scope;
- compatibility, dual-track behavior or destructive migration appears required;
- unrelated work cannot be safely partitioned;
- the public runtime/test path cannot produce meaningful evidence;
- three technically distinct repair attempts at the same root cause fail.

A typo, stale path, invalid nodeid, renamed symbol, ordinary RED failure,
review-discovered bug within scope, or need for an adjacent owner-correct file is
not by itself a replanning condition.
