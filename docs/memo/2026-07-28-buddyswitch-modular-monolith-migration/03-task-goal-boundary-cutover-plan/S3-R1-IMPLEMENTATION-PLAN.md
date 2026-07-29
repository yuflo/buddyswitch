# S3 R1 Task and Goal Cutover Completion Plan

> **For the independent executor:** use
> `superpowers:executing-plans`, root `AGENTS.md` and
> `$buddyswitch-testing`.
> Plan state: `READY`

**Goal:** Complete and prove the preserved S3 Task/Goal owner cutover without
rolling back the candidate, adding Task-specific cases to generic tests, or
creating another architecture.

**Architecture:** D-045–D-048 remain frozen. R1 repairs the packet's consumer
classification and generic proof boundaries, then verifies the already
selected explicit modular-monolith design.

## 1. Identity and authority

```text
Stage: S3 Task and Goal Boundary Cutover
Packet: BS-MM-S3-R1-20260730-01
Predecessor: BS-MM-S3-20260729-01 [REJECTED AND CONSUMED]
Starting clean base before partial candidate:
  1c99816c57196e47ddbff38bdd0d143bf5084e24
Preparation checkpoint: supplied by hub at launch
Partial candidate identities:
  S3-R1-SOURCE-SNAPSHOT.md
Exact scope:
  S3-R1-CONSUMER-AUDIT.md
Stage executor: one independent session
Acceptance owner: coordinating hub
```

## 2. Acceptance sentence

> Task owns canonical Task state and native Goal convergence in one physical
> component; every current consumer reaches it through Task Public or a typed
> contribution; generic Tool/package proofs derive their expectations from
> composition rather than accumulating product-specific exceptions; all
> retired Task paths are absent and existing product behavior is preserved.

## 3. Protected behavior

The protected contracts in the initial S3 plan remain exact:

- Tool `task_sys` with `list/get/create/cancel`;
- Demand validation before Task create;
- one active Actor Task and existing replay/conflict semantics;
- unchanged canonical Task file/schema/lock/write path;
- unchanged native Goal binding/reconciliation/recovery;
- mailbox command `task_goal.reconcile_task`;
- exact daemon order
  `demand_triage -> task_goal -> demand_orchestration`;
- Demand attention/completion evidence behavior;
- public CLI and Actor Console DTOs;
- active-Task Tool gate;
- cleanup attribution and clear/resume lifecycle;
- App Server ownership of native Goal persistence.

No Task Skill, checkpoint action, route framework, container, service locator,
compatibility module or data migration may be added.

## 4. Execution sequence

### R1.0 — Verify the handoff

- [ ] Verify `HEAD` equals the preparation checkpoint supplied by the hub.
- [ ] Verify the preparation commit changes coordinating documents only.
- [ ] Verify the exact tracked, index and untracked identities in
  `S3-R1-SOURCE-SNAPSHOT.md`.
- [ ] Verify every dirty path and every prospective new write is classified by
  `S3-R1-CONSUMER-AUDIT.md`.
- [ ] Confirm no instance/test process or active Browser belongs to S3.
- [ ] Confirm the current runtime mismatch is the expected stale-runtime state.
- [ ] Do not edit, test, commit or push on any mismatch.

### R1.1 — Reprovision before first public proof

- [ ] Build the current partial candidate through the declared PEP 517 path.
- [ ] Non-editably install it into `.buddyswitch-runtime/venv`.
- [ ] Activate and verify exact source/distribution correspondence.
- [ ] Record source, distribution and activation identity.
- [ ] Only after verification, run the two known RED targets:

```bash
./buddyswitch-test focused \
  tests/process/cli/test_env_tool_package_independence.py \
  tests/process/cli/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_private_impl_modules
```

Expected RED ownership:

- package-independence still expects the retired Task Tool directory;
- router still derives the retired Task `_impl` module and omits the Task
  component private root.

If either target fails for another reason, stop and return the complete
evidence. Do not rewrite the product to satisfy a stale test.

### R1.2 — Repair proof ownership once

- [ ] Make package-independence derive the generic dynamic package set from
  the package root. Do not add or retain Demand/Task special cases.
- [ ] Make router derive the selected private Tool implementation from the
  selected registration/module. Do not add a Task-specific conditional.
- [ ] Make the Tool runtime architecture proof derive explicit component Tool
  IDs from application composition rather than a growing manual exclusion
  set.
- [ ] Make root Task fixtures reference Task-owned status constants rather
  than copy their values.
- [ ] Replace the Web test's meaningless fixture-name source assertions with
  proof that the generic Web host contains no Task-private import or Task
  lifecycle rule.
- [ ] Retain the Task cleanup contribution proof and explicitly verify it.

These are test/proof corrections. If `src/buddyswitch/**` does not change,
record reprovision as inapplicable before the next test. If product source
does change for an ordinary in-scope implementation defect, reprovision again
before the next public test.

### R1.3 — Finish replacement and current truth

- [ ] Complete any remaining in-scope implementation needed by the frozen
  architecture.
- [ ] Update exactly the four current architecture documents.
- [ ] Prove the Task-private import allowlist:
  `modules/task/**` and `tests/support/task_fixtures.py` only.
- [ ] Prove Task imports no Demand source and Demand imports Task Public only.
- [ ] Prove old Task domain/read/Tool/Goal/client/protocol/test paths are
  absent with no forwarding modules.
- [ ] Prove one Tool, one writer, one Goal handler, one mailbox command, one
  CLI command, one Actor Console section and one cleanup contribution.
- [ ] Run `git diff --check`.

An ordinary implementation defect within the exact candidate scope may be
fixed. A new required file, public contract, data migration or architecture
choice is a stop.

### R1.4 — Focused GREEN

Run the two RED targets again, then the nearest architecture/contract group:

```bash
./buddyswitch-test focused \
  tests/process/cli/test_env_tool_package_independence.py \
  tests/process/cli/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_private_impl_modules \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/daemon/test_instance_entrypoint.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/integration/env_tool/test_cleanup.py \
  tests/integration/web/test_management_product_api.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection \
  src/buddyswitch/modules/task/tests
```

Then run the complete S3 affected preservation group defined by the initial
plan, adding the two newly classified process files. The executor may split
that group by test tier for attribution, but may not omit a target because it
passed before the partial candidate existed.

Any failure, timeout, flake or residue must be diagnosed. A later pass cannot
erase it.

### R1.5 — Frozen candidate and single FINAL

- [ ] Freeze tracked/index/untracked and activation identities.
- [ ] Confirm all focused evidence is source-equivalent to the frozen candidate.
- [ ] Confirm declared dependencies only; no ad hoc environment mutation.
- [ ] Run `./buddyswitch-test full` exactly once.
- [ ] Do not rerun FINAL after a failure.
- [ ] Prove no attributable test root, process, socket, lock, instance,
  Browser, deleted-open file or hidden dependency remains.
- [ ] Return the exact result packet and stop.

## 5. Stop conditions

Stop with `REPLANNING REQUIRED` when:

- starting identity or packet differs;
- a required file is outside the exact R1 scope;
- the known REDs fail for an unclassified reason;
- D-045–D-048 need to change;
- Task and Demand both own one transition;
- Task Public needs repository, ToolContext, daemon or Web DTOs;
- compatibility, fallback or a generic framework appears necessary;
- canonical data or behavior must migrate;
- a public test would cross changed package source before reprovision;
- a failure cannot be owned within the classified candidate;
- FINAL fails.

Do not mark the goal blocked merely because the packet has stopped. Return
once with complete evidence and let the hub decide.

## 6. Return format

```text
Packet ID and stage:
Starting preparation commit:
Starting partial-candidate identities:
Final tracked/index/untracked identities:
Final activation/source/distribution identity:
Completed R1 checkpoints:
Changed/created/deleted files:
Known RED commands, run IDs and exact expected failures:
Focused GREEN commands, run IDs, results and duration:
Affected preservation commands, run IDs, results and duration:
Single FINAL command, run ID, result and duration:
Every failure/timeout/flake/no-test/residue signal and owning disposition:
Consumer-observed Tool/Goal/Demand/Daemon/CLI/Web result:
Package-discovery and selected-private-implementation proof:
Canonical Task path/schema/write and replacement proof:
Current docs changed:
Cleanup/residual state:
Omitted checks and residual risk:
New findings or stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```
