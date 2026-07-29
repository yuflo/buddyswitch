# S3 Task and Goal Boundary Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans`. Follow root `AGENTS.md` and
> `$buddyswitch-testing`.
> Plan state: `RETIRED`
> Replacement: `S3-R1-IMPLEMENTATION-PLAN.md`

This plan records the initial design and stopped execution history. It is not
current execution authority.

**Goal:** Make Task state, Task adapters, native Goal convergence and owning
tests one physical component while preserving current behavior and deleting
every retired Task path.

**Architecture:** Task defines a narrow Demand-selection input port.
Application composition injects Demand's current public resolver, declares
the exact interleaved daemon order, and injects Task's active probe. Demand
uses only Task Public attention/evidence reads. Typed Tool, CLI, Daemon, Actor
Console and cleanup contributions connect generic hosts.

**Tech stack:** Python 3.13, current installed BuddySwitch runtime,
`setuptools.build_meta`, existing `./buddyswitch-test`.

## 1. Stage identity

```text
Stage: S3 Task and Goal Boundary Cutover
State: READY
Packet: BS-MM-S3-20260729-01
Executable source base: 8db3a07c4cca6423a1e2c789281a813800bfa2a9
Preparation checkpoint: supplied by the coordinating hub at launch
Source executable diff: empty at preparation
Owning module: Task
Stage executor: independent session selected by user
Migration lead/integration owner: coordinating hub
```

## 2. Acceptance sentence

> Task owns canonical Task state and native Goal convergence semantics in one
> component; Demand collaboration uses exact acyclic Public operations; no
> private cross-read, duplicate write path or Goal ownership confusion
> remains.

Observable path:

```text
Actor task_sys create/list/get/cancel
  -> Task-owned adapter and canonical Task state
    -> Task-owned native Goal convergence
      -> unchanged Goal/Task terminal observation
        -> Demand reads Task Public evidence/attention
          -> unchanged independent Demand decision
```

## 3. Protected contracts

No old internal Python import is protected. Direct cutover is required.

Protected current behavior/data:

- Tool ID `task_sys`; actions exactly `list/get/create/cancel`; schemas,
  authority and result/rejection envelopes;
- current Demand resolver validation before Task creation;
- at most one active Task per Actor and exact idempotency/conflict behavior;
- canonical file path, schema, lock behavior and one writer;
- Goal binding, completion, missing-goal cancellation, mismatch conflict,
  terminal-goal replacement and retry semantics;
- mailbox command `task_goal.reconcile_task`;
- daemon product order and startup/poll recovery;
- Demand attention and completion-evidence behavior;
- public CLI `task list/get`, help, errors and external-safe DTO;
- Actor Console `task_sys` shape;
- active-Task-required Tool gate behavior;
- instance clear/resume and daemon lifecycle;
- App Server Goal ownership.

There is no Task checkpoint action and no Task Skill. Do not add either.

## 4. Frozen decisions

Apply D-001, D-002, D-004–D-006, D-009–D-011, D-015–D-020,
D-025, D-027, D-028, D-031–D-044, D-045, D-046, D-047 and D-048.

## 5. Scope

Use the exact path and consumer dispositions in
`S3-OWNER-CONSUMER-MANIFEST.md`.

Allowed shared surfaces:

- foundation ModuleAssembly;
- application build/composition plus CLI/Daemon/Web entrypoints;
- daemon registration/host;
- Tool registry/context and Context Tool;
- CLI/Web host adapters;
- cleanup host contract consumption;
- Demand's two Task Public consumers and module capability export;
- classified root architecture/process/system/package tests;
- `tests/support/task_fixtures.py` plus the exact root test consumers listed in
  the owner/consumer manifest;
- four current `docs/arch/**` documents.

Expected unchanged but proof-relevant:

- `pyproject.toml`;
- `tests/runner.py`;
- App Server Goal implementation;
- canonical runtime data files.

Forbidden:

- S4 product movement;
- general plugin/DI/event/route/guard frameworks;
- new public routes or Task actions;
- Task or Demand data migration;
- compatibility aliases or import forwarding;
- edits to master ledger/decision/residue/READY documents;
- commit, push, branch switch or rebase unless the hub later authorizes it.

## 6. Proof map

| Claim | Direct proof |
|---|---|
| final Task physical root and old paths absent | rewritten Task architecture boundary test |
| source dependency graph acyclic | AST/import graph assertion including runtime wiring owner |
| resolver port preserves current validation | Task Tool response create/conflict tests |
| one writer/schema/path | Task local domain tests plus writer/path structural proof |
| exact Tool registration | explicit registry tests; old discoverable package absent |
| generic ToolContext has no Task object | architecture/context tests |
| active Task gate unchanged | `test_active_task_gate.py` |
| Goal convergence unchanged | moved local reconciliation tests |
| exact daemon order and command | daemon entrypoint plus reconciliation integration |
| Demand attention/evidence unchanged | Demand orchestration and response tests |
| CLI unchanged | public CLI Task cases |
| Actor Console unchanged | exact management product API case |
| cleanup attributes/deletes Task state safely | cleanup integration positive/negative tests |
| local tests run and wheel excludes them | runner/package process tests |
| clear/resume recovery | exact system lifecycle case |
| complete product path | frozen Goal/Demand system case |
| current docs and no residue | architecture scans and `git diff --check` |

## 7. Execution sequence

### C1 — Verify identity, reuse baseline and establish REDs

- [ ] Verify exact `HEAD` against the hub-supplied preparation checkpoint,
  clean worktree, and a preparation-doc-only delta from executable source base
  `8db3a07c4cca6423a1e2c789281a813800bfa2a9`.
- [ ] Verify the recorded activation identity, zero instances and inactive
  Browser.
- [ ] Reuse the accepted preservation evidence while source, command and
  material environment identity remain equivalent. Do not rerun it merely
  because the executor changed; if equivalence cannot be established, stop
  and return the identity mismatch to the hub.
- [ ] Add direct architecture REDs for final Task root, old-path absence,
  acyclic imports, one composition selection, exact handler order, no central
  Task host import, exact Actor Console contribution, and no Task in
  ToolContext.
- [ ] Add cleanup RED for Task attribution and guarded deletion.
- [ ] Run only those RED targets.
- [ ] Stop if a RED cannot distinguish current from target.

### C2 — Build receiving contracts and explicit composition

- [ ] Add `ActorConsoleSectionRegistration` and the sixth
  `ModuleAssembly.actor_console_sections` field.
- [ ] Extend `DaemonHandlerRegistration` with one optional application command
  factory.
- [ ] Validate duplicate/invalid section, handler, command-factory and exact
  daemon-order cases before host start.
- [ ] Add Task port/Public/module skeleton with no second owner.
- [ ] Application selects Demand and constructed Task once, injects the
  resolver and active probe, and declares the exact handler order.
- [ ] Run composition/contract GREEN.

### C3 — Move Task owner and tests atomically

- [ ] Move Task domain/read model/Tool/Goal handler/client/protocol to final
  paths.
- [ ] Move Task domain and Goal reconciliation tests local.
- [ ] Create the one root-test Task fixture adapter; root cross-component
  tests use it for setup and Task Public for observations.
- [ ] Remove every other root-test import of Task private.
- [ ] Preserve file path, schema, locks and state bytes; do not migrate data.
- [ ] Add only the Public operations in the owner manifest.
- [ ] Delete every old owner path immediately after consumers are cut.
- [ ] Do not add forwarding modules.

### Mandatory activation boundary after C2/C3 source mutation

- [ ] Complete one coherent source block.
- [ ] Build wheel with current PEP 517 path.
- [ ] non-editably install into `.buddyswitch-runtime/venv`;
- [ ] activate and verify exact source/distribution correspondence;
- [ ] only then run the first post-mutation `./buddyswitch-test`.

No RED, GREEN, milestone, affected tier or FINAL command may cross a changed
`src/buddyswitch/**` tree before this boundary.

### C4 — Cut every consumer and host over

- [ ] Task Tool uses injected resolver and its private Goal client.
- [ ] Demand orchestration/completion use only Task Public.
- [ ] Context Tool uses Task Public.
- [ ] Tool registry uses the application-injected active probe.
- [ ] `ToolContext` loses Task domain and Goal runtime objects.
- [ ] CLI uses Task registration and removes its central Task switch/import.
- [ ] Web uses Task Actor Console section and removes central Task import.
- [ ] daemon uses ordered registrations and removes central Task
  import/insertion/command list.
- [ ] cleanup includes Task-owned state paths.
- [ ] Reprovision again if this is a later coherent source mutation before
  testing.
- [ ] Run each nearest affected GREEN group.

### C5 — Replacement, package and current truth

- [ ] Assert one Task writer, one Tool registration, one Goal handler, one
  mailbox command and one Actor Console section.
- [ ] Assert old paths, imports, aliases, fallbacks and discoverable Task Tool
  package are absent.
- [ ] Assert Task imports no Demand package; Demand cross-imports target only
  Task Public; application owns the concrete resolver wire.
- [ ] Prove Task local tests run through the one runner and are absent from the
  installed distribution.
- [ ] Update the four current architecture documents.
- [ ] Run residue scans and `git diff --check`.

### C6 — Frozen candidate

- [ ] Freeze source diff and activation identity.
- [ ] Run the complete affected preservation group.
- [ ] Run new architecture, cleanup, package and lifecycle proofs.
- [ ] Run `./buddyswitch-test full` exactly once because S3 is a frozen
  repository merge candidate.
- [ ] Do not rerun FINAL after any failure; return the complete contrary
  evidence to the hub.
- [ ] Prove no process, socket, lock, instance, Browser, test root or deleted
  open file remains.
- [ ] Return the asynchronous result packet and stop.

## 8. Checkpoints

Report after C1, C2, C3/C4, C5 and C6:

```text
Packet/checkpoint:
HEAD/tracked/index/untracked identity:
Activation/source/distribution identity:
Exact completed outcome:
Files changed/moved/deleted:
All evidence including failures/timeouts/flakes/residue:
Cleanup:
Next exact action:
Stop/replan condition:
```

Do not commit a state with two live Task owners or a stale runtime. Local
commits are not required and are forbidden by this packet; the hub creates the
accepted checkpoint after review.

## 9. Stop conditions

Stop and return `REPLANNING REQUIRED` when:

- source, activation, packet, scope or unrelated dirty identity differs;
- a baseline, RED or GREEN contradicts the accepted mechanism;
- Task and Demand both claim one transition;
- Goal mutation escapes App Server owner;
- the final handler order cannot be expressed by the accepted explicit tuple;
- a Public contract needs repository, host, ToolContext or presentation DTOs;
- a generic registry/container/framework is needed;
- a behavior change or data migration appears necessary;
- any source mutation is followed by a public test before reprovision;
- a test timeout, flake, failure or cleanup residue appears;
- an unclassified file must change;
- FINAL fails.

Do not design or execute a repair packet. The hub owns replanning.
