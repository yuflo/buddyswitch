# BuddySwitch Confirmed Bug Repair Implementation Plan

> **For agentic workers:** implement through a fresh independent session using
> the companion Goal Packet. The executor owns current repository discovery and
> the shortest owner-correct implementation; paths and test targets below are
> grounded starting-point facts, not permission to preserve a stale mechanism.

**Goal:** Repair the five confirmed implementation defects F-01, F-03, F-06,
F-08 and F-09 without absorbing the deferred product/design questions F-02,
F-04, F-05 or F-07.

**Architecture:** Repair each rule at its semantic owner. Actor-to-Role mapping
comes from the canonical Identity Profile rather than reverse-parsing Actor IDs;
the generic Daemon owns schedule-delivery semantics; Web lifecycle code owns
terminal copy and stale-request ownership; CLI Runtime owns normal Web SIGINT.
No compatibility layer, fallback parser, duplicate state, general event engine,
or new testing framework is introduced.

**Tech stack:** Python 3.13, JavaScript `node:test`, BuddySwitch installed wheel
runtime, public `./buddyswitch-test` runner, JSON product state, Git.

---

## 1. Starting state and scope

Prepared from:

```text
repository: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD: 4522854 (docs: record real web actor experience audit)
upstream: origin/fea-tool at 4010434
preparation worktree before these two docs: clean; branch ahead by two documentation commits
entry activated runtime: buddyswitch 0.1.0
entry source digest: 1b448cb325b59287913d2e2c52efa4303fe277c9669f19a3c3a623e67cc23921
entry distribution digest: 85ff440cd64eeb8a895af655a7e9b2372856df8fa03741b0534f24bb9887ce7f
```

Primary source owners currently implicated:

```text
src/buddyswitch/foundation/identity/profiles.py
src/buddyswitch/modules/task/private/adapters/cli.py
src/buddyswitch/modules/task/private/read_model.py
src/buddyswitch/modules/demand/private/adapters/cli.py
src/buddyswitch/modules/demand/private/read_model.py
src/buddyswitch/modules/demand/private/state/demands.py
src/buddyswitch/modules/communication/private/adapters/cleanup.py
src/buddyswitch/modules/track/private/adapters/cleanup.py
src/buddyswitch/foundation/daemon/instance.py
src/buddyswitch/foundation/daemon/state.py
src/buddyswitch/foundation/web_runtime/assets/web-management/app.js
src/buddyswitch/foundation/cli_runtime/runtime.py
```

Current direct proof surfaces:

```text
tests/process/launcher/test_public_cli.py
tests/process/launcher/test_demand_commands.py
tests/integration/env_tool/test_cleanup.py
tests/integration/daemon/test_trigger_router.py
tests/integration/goal_mode/test_demand_orchestration.py
tests/unit/web/ui_state_lifecycle.test.js
tests/unit/web/ui_state_selection_refresh.test.js
tests/system/instance_lifecycle/test_web_command.py
```

The executor may add a narrowly owned test file when that produces a clearer
boundary than extending one of the files above. It may also omit a listed source
file when current tracing proves it need not change. It may not expand into
deferred product semantics, broad refactoring, compatibility, formatting, or an
alternate test/runtime path.

## 2. Frozen acceptance contracts

### F-01 — Actor ID is opaque; Identity Profile owns Role

Acceptance:

1. `secondary-market-investor` remains a valid reviewed Role ID.
2. Public `task list --actor <actor-id>` and `demand list/get --actor
   <actor-id>` return the canonical durable records for an Actor whose Role ID
   contains hyphens.
3. Role-scoped cleanup attributes Message and Track-comment records through
   canonical Role facts, not through Actor-ID token splitting.
4. A missing or invalid Actor Identity Profile fails closed or remains safely
   unattributed according to the existing read/cleanup contract; it must never
   guess a shortened Role.
5. No live implementation derives Role with an Actor-ID `partition`, `split`,
   prefix slice, or equivalent parser.

Owner decision:

```text
Actor ID -> Role ID is the canonical Actor Identity Profile relation.
Actor IDs are identifiers, not a reversible serialization of Role IDs.
```

Implementation direction:

- use the existing Foundation Identity Profile as the one semantic owner;
- make Task and Demand CLI reads resolve or query through that owner without
  re-encoding Role parsing in their adapters;
- keep durable reads valid after Host Instance deletion when the canonical
  identity/profile and product objects remain;
- update Communication and Track cleanup attribution to consume canonical Role
  facts, preserving the current fail-safe warning behavior for unattributable
  records;
- delete the four known unsafe reverse parsers rather than wrapping them.

Do not:

- add a “hyphen-aware” parser that scans known Role prefixes;
- infer the Role from the current Role catalog;
- make Host Instance liveness a prerequisite for durable Task/Demand reads;
- retain the old parser as fallback.

### F-03 — Matched idempotent schedule delivery is not failure

Acceptance:

1. No matching handler remains a terminal failed schedule with the existing
   no-handler diagnostic.
2. A matching handler that returns `failed` remains a terminal failed schedule
   with its real error.
3. A matching handler that validly returns `ignored` is a successful delivery
   of the scheduled trigger: the schedule becomes `delivered`, preserves the
   `dispatch_result` with `handling_status=ignored`, carries no false
   `last_error`, and is not swept again.
4. A handler that replaces/refreshes the same schedule during dispatch retains
   the current generation-safety behavior.

Owner decision:

```text
dispatch_trigger owns handler match/result facts;
sweep_due_scheduled_triggers owns schedule terminal classification.
```

The repair should distinguish `matched_count == 0`, matched failure, matched
handled, and matched ignored explicitly. Do not add a new schedule status merely
to mirror the handler result; `delivered` already means the trigger reached its
owner, not that the owner was required to mutate state.

### F-06 — Active and terminal lifecycle language are distinct

Acceptance:

1. Running/queued lifecycle operations retain progressive language such as
   `Starting`, `Stopping`, and `Deleting`.
2. Successful terminal operations use completed verbs such as `Started`,
   `Stopped`, `Resumed`, `Cleared`, `Deleted`, and `Retried`.
3. Failed operations retain the operation identity plus the actual failure.
4. Existing clear-thread result suffixes remain intact.

Fix the terminal formatter owner. Do not mutate backend operation labels merely
to make one frontend concatenation happen to read correctly.

### F-08 — Stale Actor Console errors cannot overwrite delete success

Acceptance:

1. Begin an Actor Console refresh while the Actor is selected.
2. Complete deletion and invalidate/clear that selection.
3. Reject the earlier refresh with a missing-instance/FileNotFound-style error.
4. The stale rejection must not set `state.message` or `actorCardError`, must not
   resurrect selection, and must not replace the deletion completion message.
5. A failure for the still-current selected Actor must continue to surface.

The observed code gap is asymmetric ownership checking: successful refreshes
verify selection/request generation before applying state, while
`refreshSelectedActorConsoleAndRender` currently writes a rejected request's
message without the same generation check. Establish the deferred-request RED
before editing; if that RED disproves this diagnosis, stop and return the new
boundary evidence rather than adding an error suppression fallback.

### F-09 — Ctrl-C is a normal Web CLI shutdown

Acceptance:

1. `buddyswitch-codex web` emits its one ready JSON line as today.
2. SIGINT/Ctrl-C exits the public command successfully without `Traceback` or
   `KeyboardInterrupt` in stderr.
3. The Web child, process group, port and central daemon are stopped exactly as
   the current lifecycle test requires.
4. Non-interrupt child exit codes still propagate normally.

CLI Runtime owns conversion of the parent's `KeyboardInterrupt` while waiting
in `subprocess.run` into the normal Web shutdown result. Do not globally swallow
`BaseException` and do not weaken resource-cleanup assertions.

## 3. Deferred and forbidden scope

Explicitly deferred:

```text
F-02 accepted-message/Demand/Task progress-state design
F-04 activity feedback information architecture
F-05 token accounting, latency and execution efficiency
F-07 stopped/offline/health presentation and duplicated action guidance
```

Forbidden:

- changing Role IDs or forbidding hyphens;
- changing the Actor-ID format to encode a newly parseable Role field;
- state migration, dual reads/writes, compatibility aliases or fallbacks;
- a general identity lookup registry, event bus, retry engine, request manager,
  static analyzer, or second test entry;
- weakening current no-handler, handler-failure, destructive-confirmation,
  process-cleanup, or malformed-input behavior;
- editing unrelated architecture migration history;
- stage, commit, push, merge, or branch operations in the execution session.

## 4. Implementation sequence

### Task 0 — Freeze entry facts and discover current proof

- [ ] Read root `AGENTS.md`, `$buddyswitch-testing`, this plan, and the Goal
  Packet completely.
- [ ] Record HEAD, branch/upstream, tracked diff, index, non-ignored untracked
  identity, activation status, Python/Node versions, and attributable runtime
  resources.
- [ ] Re-run current `rg` discovery for the five owner symbols and four known
  Actor-ID reverse parsers. Treat the lists in this plan as review input.
- [ ] Confirm unrelated work is absent or partitionable. Preserve it if present.

### Task 1 — Establish all five exact REDs before source mutation

Test-only changes do not alter installed package source identity. Add the
smallest direct regression for each frozen acceptance contract and run each
through `./buddyswitch-test focused` on the entry runtime.

- [ ] F-01 RED: create canonical Identity Profile and Task/Demand fixtures for a
  `secondary-market-investor` Actor; public filtered reads must currently return
  empty/fail and the new assertions must fail for that reason.
- [ ] F-01 cleanup RED: a Message and Track comment owned by the same hyphenated
  Role must be attributed to the complete Role during role-scoped cleanup; the
  assertion must fail because current code produces `secondary`.
- [ ] F-03 RED: add a scheduled trigger with one matching handler returning
  `ignored`; assert terminal `delivered`, zero failures, no error, one sweep.
- [ ] F-06 RED: assert terminal text for supported lifecycle actions uses
  completed verbs while an active operation remains progressive.
- [ ] F-08 RED: use a deferred Actor Console request, invalidate selection through
  terminal deletion, reject the stale request, and assert the deletion result is
  still the sole user message. Also retain/prove the current-request failure case.
- [ ] F-09 RED: strengthen the real Web command SIGINT test to assert exit code
  zero and absence of traceback/KeyboardInterrupt while retaining all cleanup
  assertions.
- [ ] Record each RED separately. Setup, collection, runtime mismatch, timeout or
  unrelated failure is not valid RED.

Candidate starting targets, to be validated rather than copied blindly:

```text
tests/process/launcher/test_public_cli.py
tests/process/launcher/test_demand_commands.py
tests/integration/env_tool/test_cleanup.py
tests/integration/daemon/test_trigger_router.py
tests/unit/web/ui_state_lifecycle.test.js
tests/unit/web/ui_state_selection_refresh.test.js
tests/system/instance_lifecycle/test_web_command.py
```

### Task 2 — Repair F-01 at the Identity owner

- [ ] Make the existing Identity Profile the sole Actor-to-Role lookup.
- [ ] Update Task and Demand public CLI reads to consume the canonical relation
  and return full hyphenated Role IDs.
- [ ] Update Communication/Track role-scoped cleanup attribution to consume the
  same truth and preserve safe unattributed behavior.
- [ ] Remove every live Actor-ID-to-Role reverse parser found in Task, Demand,
  Communication and Track.
- [ ] Inspect the resulting dependency direction: product modules may depend on
  the Foundation Identity public contract; Foundation Identity must not depend
  on product modules or cleanup DTOs.
- [ ] Do not run the public test runner until the first runtime reprovision gate.

### Task 3 — First runtime gate and F-01 GREEN/IMPACT

- [ ] Build a fresh wheel from this worktree, force-install it non-editably into
  `.buddyswitch-runtime/venv`, activate it against this source root, and run
  runtime `verify` and `status`.
- [ ] Confirm source/distribution correspondence and absence of build residue.
- [ ] Run the exact F-01 CLI and cleanup regressions, batching compatible targets.
- [ ] Run only direct affected Identity/Profile, public CLI and cleanup tests
  discovered from current references.
- [ ] Record GREEN/IMPACT evidence and all contrary signals.

### Task 4 — Repair F-03 at the Daemon schedule owner

- [ ] Make schedule terminal classification consume handler match/result facts
  without collapsing ignored, unmatched and failed outcomes.
- [ ] Preserve the current dispatch snapshot/generation guard.
- [ ] Do not change the HandlerResult vocabulary or product-specific Demand
  handler behavior.
- [ ] Reprovision/activate/verify after the source edit before the next public
  runner command.
- [ ] Run the exact matched-ignored regression plus the existing no-handler,
  handler-failure, delivered-once and refreshed-schedule tests.
- [ ] Add the direct Demand orchestration idempotent/ignored proof only if current
  target discovery shows it is not already covered by the exact generic test.

### Task 5 — Repair F-06, F-08 and F-09 at Web/CLI owners

- [ ] Give the Web terminal formatter action-aware completed language while
  retaining progressive and failure text.
- [ ] Apply stale rejected Actor Console results only when the captured actor,
  selection generation and console request generation still own current UI
  state. Keep current-request failures visible.
- [ ] Treat `KeyboardInterrupt` around the Web child wait as normal shutdown and
  preserve `finally` cleanup and ordinary child exit-code propagation.
- [ ] Inspect other terminal/error paths in the same functions for the same
  ownership invariant; do not stack a delete-only or FileNotFound-only catch.
- [ ] Reprovision/activate/verify once after this coherent source cohort.
- [ ] Run the exact F-06/F-08 JavaScript regressions and F-09 system regression.
- [ ] Run direct affected Web lifecycle/selection and CLI Web lifecycle tests.

### Task 6 — Replacement, review and one frozen FINAL

- [ ] Prove no Actor-ID Role parser remains in live source. A bounded `rg` scan is
  supplementary evidence, not a replacement for behavioral tests.
- [ ] Inspect the final diff for copied identity rules, branch-local error
  suppression, hidden fallback, weakened assertions, unrelated cleanup, or new
  abstractions.
- [ ] Confirm all review-driven executable edits are complete.
- [ ] Reprovision again only if executable source changed after the preceding
  gate; otherwise reuse the current verified runtime identity.
- [ ] Freeze HEAD/diff/untracked/runtime identities and resource baseline.
- [ ] Run `./buddyswitch-test full` exactly once for repository-wide acceptance.
- [ ] If FINAL fails, keep the signal, diagnose its owner, run only exact/affected
  repair proof, reprovision if source changes, then run one new FINAL only after
  the candidate freezes again. Never blind-rerun.
- [ ] Prove cleanup: no attributable process, port, socket, lock or test root;
  preserve unrelated pre-existing resources.
- [ ] Return the complete result packet and stop without Git operations.

## 5. Efficient verification design

The intended command economy is:

```text
current activated runtime
  -> direct RED proofs for every distinct behavior boundary
  -> F-01 source cohort
  -> provision/activate/verify #1
  -> F-01 exact + affected GREEN
  -> F-03 source cohort
  -> provision/activate/verify #2
  -> F-03 exact + affected GREEN
  -> F-06/F-08/F-09 source cohort
  -> provision/activate/verify #3
  -> Web/CLI exact + affected GREEN
  -> review/freeze
  -> one full FINAL
```

Efficiency rules:

1. Do not run `full` during development.
2. Do not rerun an unchanged command merely because responsibility changed.
3. Batch compatible explicit targets, but keep the resource-owning Web SIGINT
   system test in its runner-managed exclusive interval.
4. Test-only changes before source mutation reuse the entry activated runtime.
5. Every `src/buddyswitch/**` mutation is followed by provision/activate/verify
   before another public-runner command.
6. Reuse identity-valid GREEN evidence when a later cohort cannot affect it;
   rerun only the direct shared boundary when dependency tracing says it changed.
7. Mechanically invalid suggested node IDs may be corrected from current
   collection facts without a coordinating round trip; report the correction.
8. Any failure, timeout, flake or residue supersedes older passing evidence until
   its owner and disposition are recorded.

## 6. Acceptance evidence required

The return packet must show:

| Proof class | Required observation |
|---|---|
| Product | Hyphenated-Role Task/Demand public CLI reads return the seeded records; Web SIGINT is quiet and clean. |
| Contract | Matched ignored schedule is delivered; unmatched/failed remain failures; stale deleted-Actor error cannot overwrite success. |
| Architecture | Identity Profile is the sole Actor-to-Role owner; no product module or generic host reverse-parses Actor IDs. |
| Replacement | Four known reverse parsers and any equivalent live parser are absent; no fallback/alias remains. |
| Operations | Delete/SIGINT terminal truth is coherent and no attributable resource remains. |

Required evidence identity follows `$buddyswitch-testing`: source, exact command,
environment/runtime identity, result, all contrary signals, cleanup identity,
claim, validity and residual risk.

## 7. Stop conditions

Stop and return `REPLANNING REQUIRED` only when current repository evidence shows:

- Identity Profile is not durable for the affected consumer and fixing that
  requires canonical data migration or a new protected contract;
- the F-08 deferred-request RED does not reproduce the observed stale-error
  ownership gap;
- a required owner lies outside the authorized source/test boundaries;
- a compatibility/fallback/dual-track mechanism appears necessary;
- unrelated dirty work overlaps a required write and cannot be partitioned;
- the public runner or declared runtime cannot produce meaningful evidence;
- the same repair hypothesis fails three times, requiring architecture review.

A stale line number, renamed test, or mechanically invalid suggested target is
not a stop condition when the executor can rediscover the equivalent current
owner and proof inside the frozen acceptance boundary.
