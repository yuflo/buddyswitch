# S3 Initial Execution Return Review

> Review result: `REPLANNING REQUIRED`
> Retired packet: `BS-MM-S3-20260729-01`
> Product candidate: preserved in place, not accepted
> Review date: 2026-07-30

## 1. Outcome

The independent executor stopped correctly before editing an unclassified
file. The initial packet is rejected and consumed. It may not be resumed.

The stop does **not** reject the Task boundary design or require rolling back
the partial candidate. It rejects the packet's claim that its consumer
manifest was complete.

The hub did not edit product source, tests or runtime while reviewing the
return.

## 2. Exact returned condition

The current partial candidate requires
`tests/process/cli/test_env_tool_package_independence.py` to change because
Task Tool is no longer a filesystem-discovered package. The old manifest did
not classify that file and simultaneously required work to stop on any
unclassified mutation.

The executor therefore had no valid next action:

```text
required consumer change
  -> file outside declared write scope
    -> mandatory stop
```

This is a coordinating-hub scope defect, not executor indecision.

## 3. Root cause

The initial READY audit searched and classified:

- direct Python imports;
- literal retired source paths;
- known host and external consumer paths.

It did not systematically classify:

- data-driven product/tool ID sets;
- generated module names;
- generated filesystem paths;
- directory/package discovery assertions;
- subprocess scripts with a different application-activation state.

The incomplete method allowed a manifest to look exhaustive while missing a
consumer whose coupling was represented by the string `task_sys`, not by a
direct import of the retired Task owner.

## 4. Detailed review findings

### F-S3-R1-001 — incomplete package-discovery consumer classification

`tests/process/cli/test_env_tool_package_independence.py` hard-codes
`task_sys` as a discovered package and asserts that
`src/buddyswitch/env/tools/task_sys` exists. It must change.

The repair must remove the generic test's product-specific package inventory,
not merely delete one set member. The test should derive the dynamic package
set from the package directory and continue proving registry/package
correspondence and sibling isolation.

### F-S3-R1-002 — generated private-module expectation missed

`tests/process/cli/test_env_tool_router.py` generates the expected private
implementation module as:

```text
buddyswitch.env.tools.{tool}._impl
```

with one Demand-specific exception. The Task move makes this wrong. Adding a
second Task-specific exception would create the same maintenance hotspot.
The expectation must instead derive from the selected registration/module and
recognize component-private Tool implementations generically.

### F-S3-R1-003 — one changed proof was absent from the exact manifest

`tests/integration/env_tool/test_cleanup.py` is already changed in the partial
candidate to prove Task cleanup attribution. The old proof map implied this
work, but the exact root-consumer list omitted the file. The R1 scope names it
explicitly.

### F-S3-R1-004 — candidate proof drift

The partial candidate contains two proof-quality defects within already
authorized files:

- `tests/support/task_fixtures.py` copies Task status strings instead of
  referencing the Task owner;
- the Web integration test mechanically changed two source assertions into
  checks for `task_fixtures.COMPLETED/CANCELED`, strings that production Web
  source could never contain.

R1 must remove the copied truth and replace the meaningless assertions with
owner/boundary-relevant proof.

### F-S3-R1-005 — central test classification should derive from composition

`tests/unit/architecture/test_tool_runtime_contract.py` now manually subtracts
Demand and Task IDs from the discovered-package set. That would require the
same central edit for every later component Tool cutover.

R1 must derive explicitly contributed Tool IDs from the selected application
assembly and use that projection to distinguish explicit component Tools from
remaining dynamic packages. Product Tool/action completeness remains a
separate current contract.

## 5. Architecture review

The existing partial product candidate is admitted for R1 continuation:

- one physical `modules/task/**` owner exists;
- the retired Task domain, read, Tool, Goal and test owners are deleted;
- Task source imports no Demand package;
- Demand imports Task Public only;
- application composition owns the concrete resolver, active probe and exact
  daemon order;
- generic ToolContext, registry, CLI, Web and daemon hosts no longer import
  Task private state;
- Task domain bytes are unchanged and moved Task tests preserve their prior
  behavior with path/import updates;
- no compatibility alias, fallback owner or duplicate Task registration was
  found.

This is a static admission, not runtime acceptance. The installed runtime is
intentionally stale relative to the candidate, so no public test result is
claimed.

## 6. Corrective action

R1 resumes the preserved candidate through a new complete scope. It:

1. verifies the exact dirty candidate identity;
2. reprovisions the installed runtime before any public test;
3. captures the two known failing consumer proofs as RED;
4. repairs the generic tests at their ownership boundary;
5. closes the candidate proof drift;
6. finishes the four current architecture documents;
7. runs focused affected proof and one frozen FINAL;
8. returns without committing or beginning S4.

The detailed scope is in `S3-R1-CONSUMER-AUDIT.md`. The sole replacement
packet is `BS-MM-S3-R1-20260730-01`.
