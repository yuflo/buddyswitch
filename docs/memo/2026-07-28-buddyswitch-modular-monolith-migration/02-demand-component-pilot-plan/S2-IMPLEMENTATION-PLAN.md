# S2 Demand Component Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task by task. Follow root
> `AGENTS.md` and `$buddyswitch-testing`.
> Plan state: `ACCEPTED / CONSUMED`

This plan is closed by `S2-ACCEPTANCE.md` and is not an active execution
surface.

**Goal:** Make Demand one physical, explicitly composed product module while
preserving its current consumer-visible behavior and canonical state.

**Architecture:** `modules.demand.module.DEMAND` is the only application
selection. It returns one passive typed assembly. Generic hosts receive only
their own registrations; cross-component callers import only Demand Public.
Every former Demand implementation, Skill and owning test path is deleted in
the same cutover.

**Tech stack:** Python 3.13, existing installed BuddySwitch runtime,
`setuptools.build_meta`, existing `./buddyswitch-test`.

## 1. Stage identity

```text
Stage: S2 Demand Component Pilot
Charter: ../02-demand-component-pilot.md
State: READY
Source commit: 28ca25d93b84c0165fa4cd6f92744744c1df5d67
Source dirty diff: empty at preparation; coordinating docs only at handoff
Owning module/capability: Demand
Stage executor: independent session selected by user
Migration lead: coordinating session
Integration owner: coordinating session; executor may edit only classified shared files
Plan review date: 2026-07-29
```

## 2. Acceptance sentence

> Demand domain, state, adapters, assets, exported Skills and local tests live
> under one Demand root; the application selects Demand once; generic hosts
> and other components use typed contributions or Demand Public contracts and
> know no Demand-private detail.

Consumer path:

```text
IM/Track/CLI/Tool/Daemon/Actor action
  -> Demand Public operation or Demand-owned adapter
    -> typed host registration
      -> unchanged Demand state/result/recovery observation
```

## 3. Final topology

```text
src/buddyswitch/
  application/
    build.py
    composition.py
    entrypoints/**
  foundation/
    composition/__init__.py
  modules/
    __init__.py
    demand/
      __init__.py
      module.py
      public/
        __init__.py
        operations.py
      private/
        domain/demand_sys.py
        read_model.py
        state/demands.py
        adapters/
          cli.py
          cleanup.py
          tool/{__init__.py,tool.py,_impl.py}
          daemon/{__init__.py,demand_sys_daemon_adapter.py,demand_triage_runtime.py,demand_triage_handler.py,demand_orchestration_handler.py}
      skills/{demand-triage,demand-orchestration}/SKILL.md
      tests/
        unit/**
        integration/**
```

No extra empty directory is required. Private subdirectories may use the
minimum `__init__.py` files required by the package.

## 4. Scope ledger

### OWNER — move/delete atomically

| Current path | Final disposition |
|---|---|
| `src/buddyswitch/env/domain/demand_sys.py` | MOVE to Demand private domain |
| `src/buddyswitch/env/domain/demand_read.py` | MOVE to Demand private read model |
| `src/buddyswitch/env/repos/demands.py` | MOVE to Demand private state |
| `src/buddyswitch/env/tools/demand_sys/**` | MOVE to Demand private Tool adapter; DELETE old directory |
| `src/buddyswitch/launcher/demand_sys_daemon_adapter.py` | MOVE behind Demand Public inbound operation |
| `src/buddyswitch/launcher/demand_triage_runtime.py` | MOVE to Demand private daemon adapter |
| `src/buddyswitch/launcher/demand_triage_handler.py` | MOVE to Demand private daemon adapter |
| `src/buddyswitch/launcher/demand_orchestration_handler.py` | MOVE to Demand private daemon adapter |
| `src/buddyswitch/skills/shared/demand-triage/**` | MOVE to Demand Skill export |
| `src/buddyswitch/skills/shared/demand-orchestration/**` | MOVE to Demand Skill export |
| `tests/unit/demand_sys/**` | MOVE to Demand local unit tests |
| `tests/integration/demand_sys/**` | MOVE to Demand local integration tests |

### CREATE

- `src/buddyswitch/modules/__init__.py`;
- `src/buddyswitch/modules/demand/__init__.py`;
- `src/buddyswitch/modules/demand/module.py`;
- `src/buddyswitch/modules/demand/public/{__init__.py,operations.py}`;
- minimum private package `__init__.py` files;
- `src/buddyswitch/foundation/composition/__init__.py`;
- `src/buddyswitch/application/{build.py,composition.py}`;
- `src/buddyswitch/runtime_support/skill_contracts.py`.

### HOST CONTRACT / COMPOSITION — MODIFY

- `src/buddyswitch/env/tool_runtime/{definition.py,registry.py,context.py,native_mcp.py}`;
- `src/buddyswitch/runtime_kernel/dispatcher.py`;
- `src/buddyswitch/launcher/{daemon_contracts.py,instance_daemon.py,cli_contract.py,cli.py,actor_environment.py,codex_config.py,env_tool_mcp_server.py}`;
- relevant `src/buddyswitch/application/entrypoints/*.py`;
- `src/buddyswitch/runtime_support/{env_manifest.py,runtime_skills.py,env_cleanup.py}`;
- `src/buddyswitch/catalog/manifest.toml`;
- `pyproject.toml`;
- `tests/runner.py`.

### CONSUMER — MODIFY

- `src/buddyswitch/env/tools/task_sys/_impl.py`;
- `src/buddyswitch/launcher/im_wake_handler.py`;
- `src/buddyswitch/launcher/track_comment_added_handler.py`.

### PROOF — MOVE/MODIFY

- moved Demand local tests;
- `tests/unit/architecture/test_demand_sys_boundaries.py`;
- `tests/unit/architecture/test_package_contract.py`;
- `tests/unit/architecture/test_tool_runtime_contract.py`;
- `tests/unit/daemon/test_instance_entrypoint.py`;
- `tests/unit/actor/test_runtime_skills.py`;
- `tests/unit/launcher/test_actor_environment.py`;
- `tests/unit/env_tool/{test_native_mcp_server.py,test_schema_contract.py,test_semantic_contract.py}`;
- `tests/integration/env_tool/{test_cleanup.py,test_response_demand.py,test_context_binding.py}`;
- `tests/integration/runtime/test_runless_contract.py`;
- `tests/process/launcher/{test_demand_commands.py,test_bootstrap_config.py,test_public_cli.py}`;
- `tests/process/cli/test_env_native_mcp_projection.py`;
- `tests/process/package/{test_distribution_install.py,test_runtime_activation.py}`;
- affected Task/Goal/IM/Track/root system tests named in verification.

### CURRENT DOC — MODIFY

- `docs/arch/demand-sys-architecture.md`;
- `docs/arch/daemon-service-architecture.md`;
- `docs/arch/task-sys-architecture.md` only for the current Public edge.

### Forbidden

- any second Demand package, alias or forwarding import;
- any `pkgutil` component discovery;
- new Web behavior;
- Task/Goal physical migration;
- RoleHost implementation;
- unrelated formatting/renames;
- master ledger, decision log, residue statuses or stage acceptance.

## 5. Protected contracts and frozen behavior

No internal Python import path is protected; S2 uses direct Forward cutover.

Protected current product/data contracts:

- Tool ID `demand_sys`, actions `list/get/resolve_inbound/complete`, schemas,
  permissions, visibility and result/error envelopes;
- CLI `demand list --actor` and `demand get <id> --actor`, help and errors;
- trigger `demand.ingress.triage`;
- Skill IDs `demand-triage` and `demand-orchestration`;
- schema 5 aggregate path, lock path and single atomic writer;
- one-use Side capability and actual-thread checks;
- D2 recovery and Task/Goal orchestration behavior;
- Actor start/status/input/interrupt/compact/clear/resume/stop/delete;
- parent/Side Tool and Skill projection;
- current public cleanup JSON shape, extended only with Demand paths/category.

Failure must leave canonical Demand state unchanged where it does today.
Restart/recovery remains receipt, pool-revision, Task/Goal and handler-state
driven.

## 6. Frozen decisions

Apply D-001, D-002, D-004–D-006, D-009–D-011, D-015–D-020, D-025,
D-027, D-028, D-031–D-037 and D-039–D-043.

## 7. Accepted pre-READY evidence

See `S2-BOUNDARY-DESIGN-AND-PREFLIGHT.md`.

## 8. Proof map

| Claim | Exact proof | Expected entry |
|---|---|---|
| module-local focused target unsupported | temporary final-shaped target through public runner | RED exit 2, already captured |
| passive assembly and duplicate/invalid failure | architecture/composition tests | RED before build, GREEN after |
| one Demand owner/path/writer | rewritten Demand boundary test | RED on old topology, GREEN after |
| hosts know no Demand private | AST/import/source assertions | RED on current source |
| Tool remains exact four-action surface | existing Tool contract/wire tests | PASS baseline then GREEN |
| CLI unchanged | `test_demand_commands.py` | PASS baseline then GREEN |
| Side/Parent Skill and capability unchanged | bootstrap, native MCP and triage flow tests | PASS baseline then GREEN |
| state path/schema/write unchanged | local repository/lifecycle tests | PASS baseline then GREEN |
| cleanup selects role/all-data safely | cleanup integration tests | RED for missing Demand category then GREEN |
| wheel includes Skills/excludes tests | package process tests | RED after move before package-data update, GREEN after |
| complete Actor/Goal path | frozen affected group | PASS baseline then final GREEN |
| old paths absent | package/Demand architecture scans | RED until replacement task complete |

## 9. Task sequence

### Task 1 — Freeze REDs and host contracts

- [ ] Verify packet source and unrelated dirty scope.
- [ ] Recreate the module-local runner RED.
- [ ] Add architecture REDs for one explicit module selection, typed fields,
  duplicate/invalid failure, forbidden private imports and exact old paths.
- [ ] Add cleanup RED for role/all-data Demand aggregate selection and escape
  rejection.
- [ ] Run only the focused RED targets and record run IDs.
- [ ] Stop if any RED cannot distinguish current from target.

### Task 2 — Build passive composition and typed receiving contracts

- [ ] Add the exact five-field `ModuleAssembly`.
- [ ] Add Daemon, Tool, CLI, Skill and cleanup receiving types at their host
  owners.
- [ ] Add `application/composition.py` with only `(DEMAND,)`.
- [ ] Add application build/activation validation.
- [ ] Make duplicate/invalid cases fail before host startup.
- [ ] Run focused composition/contract GREEN.

No handler, Tool, command, Skill or planner name may appear in application
composition.

### Task 3 — Move Demand owner and Public consumers

- [ ] Move the domain, read model, repository, adapters and Skills once.
- [ ] Preserve schema/path/lock/write bytes and behavior.
- [ ] Expose only `resolve_demand_ref` and `enqueue_inbound` from Public.
- [ ] Update Task, IM and Track consumers to Public.
- [ ] Move owning unit/integration tests under the module.
- [ ] Do not leave import forwarding modules.
- [ ] Run local Demand and cross-consumer focused GREEN.

### Task 4 — Cut Tool, capability, CLI and Daemon hosts over

- [ ] Explicitly register Demand Tool and remove its discovered package.
- [ ] Replace Demand-specific invocation fields/branches with the generic
  bound capability contract.
- [ ] Remove Demand domain/application access from `ToolContext` and Broker.
- [ ] Inject daemon and CLI registrations from the application.
- [ ] Preserve Tool catalog, role authority, CLI help/error and handler order.
- [ ] Run Tool/native MCP/CLI/Daemon/Side integration GREEN.

### Task 5 — Cut Skill, packaging, runner and cleanup over

- [ ] Assemble the two Skill exports and delete their central path rows.
- [ ] Keep Role Skill ID selections current.
- [ ] Derive parent/Side defaults from exports/action metadata.
- [ ] Add module Skill package data and prove module tests absent from wheel.
- [ ] Add module local unit/contract/integration roots to the one runner,
  exactly once in focused/full discovery.
- [ ] Inject Demand cleanup contribution and preserve public cleanup response.
- [ ] Reprovision the non-editable runtime before any installed-package GREEN.
- [ ] Run runner/package/Actor/cleanup GREEN.

### Task 6 — Replacement and current truth

- [ ] Delete every old owner, adapter, Skill and owning-test path.
- [ ] Assert no production import of `modules.demand.private` exists outside
  `modules/demand`.
- [ ] Assert foundation/hosts do not import `modules.demand`.
- [ ] Assert application imports only `modules.demand.module`.
- [ ] Assert scanner does not discover Demand and exactly one Tool exists.
- [ ] Update the three current architecture documents.
- [ ] Run residue scans and `git diff --check`.

### Task 7 — Frozen final candidate

- [ ] Freeze exact diff and installed activation identity.
- [ ] Run the complete affected 92-test/65-subtest group.
- [ ] Run package, cleanup, CLI, Daemon and lifecycle additions.
- [ ] Run `./buddyswitch-test full` because S2 is a runtime merge candidate.
- [ ] Confirm no process/socket/lock/temp/test-root residue.
- [ ] Return the asynchronous result packet and stop.

## 10. Runtime reprovision rule

After the first `pyproject.toml` or `src/buddyswitch/**` mutation, the existing
activation is stale. No GREEN claim is valid until the executor explicitly:

1. builds one clean wheel through `pip wheel --no-build-isolation`;
2. creates/replaces the checkout-local runtime venv;
3. installs the wheel non-editably;
4. runs the installed activation entrypoint against the current source;
5. verifies exact source/distribution correspondence.

Product launchers and Actor start must not perform this operation.

## 11. Stop conditions

Stop and return REPLAN evidence if:

- another real Public capability is required;
- a Host contribution needs an untyped bag or component discovery;
- canonical state path/schema/write must change;
- Demand behavior must change to complete the move;
- old and new registrations must coexist;
- another component must be physically migrated;
- package/runner final topology contradicts the accepted preflight;
- unrelated dirty work overlaps required shared files.
