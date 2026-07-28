# S1 Entry Baseline Repair Goal Packet

> Packet state: READY
> Packet ID: `BS-MM-S1-E0-20260728-01`
> Stage: S1 entry prerequisite; not S1 migration
> Master state: S1 PROPOSED / runtime migration unauthorized

## 1. Copy-paste independent task request

```text
Create and pursue this goal in the independent task:

Restore the three source-bound current-baseline contracts F-026–F-028 required
before BuddySwitch S1 can begin: align the Web-interface architecture proof to
the current accepted document, prove Parent/Main Context exposes the filtered
Demand Tool catalog rather than the side-only resolve action, and remove the
Runtime Kernel eager package-import cycle so direct Tool dispatch succeeds.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/ENTRY-BASELINE-GOAL-PACKET.md

Follow root AGENTS.md and $buddyswitch-testing. Reuse the recorded isolated RED
evidence when source identity matches. Do not start package/runtime migration,
do not edit the master migration ledgers, do not stage or commit, and do not
begin another goal. When the required focused verification finishes, return
the packet's exact asynchronous result and stop. I will bring the result back
to the coordinating task for acceptance.
```

## 2. Packet identity

```text
Packet ID: BS-MM-S1-E0-20260728-01
Prepared: 2026-07-28, coordinating hub
Worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Branch: fea-tool
Source commit: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
Tracked patch at preparation: empty
Indexed patch at preparation: empty
Untracked scope: coordinating-owned docs/memo architecture/migration pack
Predecessor: S0 ACCEPTED
Formal S1 state: PROPOSED
```

At start, record current `HEAD`, tracked/index patch identities and every
non-ignored untracked file. The hub documents are unrelated dirty work to
preserve.

## 3. Goal and acceptance

Goal:

> Restore F-026–F-028 only, making the current source a trustworthy
> behavior-preservation baseline for formal S1 preparation.

Acceptance:

> Current architecture proof, parent Tool catalog and direct Tool dispatch
> agree with their accepted owners; the exact isolated and 21-file focused
> proofs pass with clean cleanup; no package/runtime migration has begun.

Consumer paths:

```text
architecture contract -> current docs/arch -> architecture test
Parent/Main context.get -> parent catalog projection -> visible Tool actions
direct Tool import -> daemon protocol import -> Runtime Kernel package boundary
```

Non-goals:

- `src/buddyswitch` creation;
- `pyproject.toml` or dependency changes;
- launcher/process/runtime identity changes;
- Actor workspace changes;
- Demand/Task semantics redesign;
- S1 migration, future stages or full-suite acceptance.

## 4. Read order

1. root `AGENTS.md`;
2. `$buddyswitch-testing` and its discovery/evidence/escalation references;
3. `00-source-snapshot.md`;
4. `00-entry-baseline-repair-plan.md`;
5. this packet;
6. exact current source/tests named by the plan.

Do not use the historical HTML memo as current architecture.

## 5. Scope

```text
OWNER:
  scripts/runtime_kernel/__init__.py

PROOF:
  tests/unit/architecture/test_external_control.py
  tests/integration/runtime/test_runless_contract.py
  tests/process/cli/test_black_box_tool_runtime.py

CURRENT DOC, conditionally:
  docs/arch/web-interface-call-architecture.md

HUB-OWNED DIRTY WORK TO PRESERVE:
  untracked docs/memo/2026-07-23-*
  untracked docs/memo/2026-07-28-*

FORBIDDEN:
  every other production/test/current-doc file
  migration ledgers, decisions, finding/residue state
  package/runtime/Actor migration files
  staging, commit, push, merge or another worktree
```

No unclassified file may be modified. If formatting tools touch another file,
restore only that task-created change without touching user work.

## 6. Frozen behavior and decisions

- current Web/CLI/Actor Session/IM/product owner boundaries remain those in
  `docs/arch/web-interface-call-architecture.md`;
- Parent/Main cannot invoke or discover side-only
  `demand_sys.resolve_inbound` through `context.get`;
- the global registry retains the side-only action;
- Runtime Kernel package initialization has no eager Broker side effect;
- there is no public compatibility obligation for the unused package-root
  `dispatch_runtime_request` re-export;
- no canonical state, external API or user data changes;
- success/failure envelopes and Tool behavior are otherwise unchanged.

Applicable decisions: D-001, D-004, D-018, D-020, D-025, D-027, D-031,
D-032.

## 7. Execution checkpoints

### E0.1 F-026

Use RED run `dc292766c7344aa8b9e7c9811fb98b8a`. Compare the current document and
test completely. Change the proof to assert current durable semantics; do not
restore old prose to satisfy it.

Run the exact F-026 node ID.

### E0.2 F-027

Use RED run `3664a01b7c1a4cbca9ae0bf72c718245`. Preserve the parent/global
catalog distinction from the plan. Run the exact F-027 node ID.

### E0.3 F-028

Use RED run `fb3d4976cf654a00bd6111179729d52d`. Confirm no package-root
dispatch consumer, make the package initialization side-effect free, and run
the two exact F-028 node IDs.

### E0.4 Direct affected baseline

Run exactly:

```bash
./buddyswitch-test focused tests/unit/architecture/test_repo_contracts.py tests/unit/architecture/test_external_control.py tests/unit/launcher/test_actor_environment.py tests/unit/actor/test_runtime_skills.py tests/integration/app_server/test_client.py tests/integration/daemon/test_central_service.py tests/integration/runtime_broker/test_broker.py tests/integration/runtime/test_runless_contract.py tests/process/launcher/test_public_cli.py tests/process/launcher/test_bootstrap_config.py tests/process/launcher/test_instance_commands.py tests/process/cli/test_clean_runtime_environment.py tests/process/cli/test_env_native_mcp_projection.py tests/process/cli/test_black_box_tool_runtime.py tests/process/services/test_app_server_process_group.py tests/process/services/test_central_daemon_lifecycle.py tests/process/services/test_instance_daemon_lifecycle.py tests/process/services/test_runtime_broker_behavior.py tests/process/services/test_runtime_broker_lifecycle.py tests/process/launcher/test_browser_cockpit.py tests/process/browser/test_runtime_manager_cli.py
```

This command is the MILESTONE proof for the entry repair. `full` is forbidden.

## 8. Replacement and absence

This repair removes no product feature. It must prove absence of:

- old exact-prose assertions that no longer describe the current document;
- equality between parent-visible and global Demand catalogs;
- eager `from .broker import dispatch_runtime_request` package initialization;
- a lazy alias, fallback or compatibility re-export replacing that eager
  import.

## 9. Stop and return early

Stop without repair broadening if any condition in
`00-entry-baseline-repair-plan.md` §5 occurs, if source identity changed before
your edits, or if the allowed files already contain unrelated tracked edits.

Return evidence and a proposed replan. Do not improvise a wider change.

## 10. Required asynchronous return

```text
Packet ID: BS-MM-S1-E0-20260728-01
Goal status:
Starting HEAD / tracked patch / index patch / untracked identity:
Exact final diff and changed files:
E0.1 result and run ID:
E0.2 result and run ID:
E0.3 result and run ID:
E0.4 milestone result and run ID:
Consumer-observed contract:
Cleanup/residual state:
F-026/F-027/F-028 closure proposal:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed prerequisite ACCEPTED / REJECTED:
```

Stop after returning this block. Do not wait on or contact the coordinating
task; the user will bring the result back.
