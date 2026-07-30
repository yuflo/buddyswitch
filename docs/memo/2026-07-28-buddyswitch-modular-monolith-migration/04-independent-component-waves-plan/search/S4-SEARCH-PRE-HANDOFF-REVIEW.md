# S4 Search Pre-Handoff Review

> Review result: initial packet rejected before execution
> Rejected packet: `BS-MM-S4-SEARCH-20260730-01`
> Successor packet: `BS-MM-S4-SEARCH-R1-20260730-01`
> Product source changed by review: no

## 1. Why the initial packet was not handed off

The maintainer requested a second review against the S2 and S3 delivery
lessons. The hub re-read the live testing contract, inspected every current
Search representation and found four packet defects.

### F-S4-SEARCH-P1 — manufactured RED for a refactor

The initial packet required a new structural test to fail before moving
Search. Search behavior is not changing; this lane is a behavior-preserving
owner refactor. `$buddyswitch-testing` explicitly requires an identity-valid
current GREEN baseline and says not to manufacture failure for a refactor.

Correction:

- reuse the recorded Search and consumer GREEN baselines;
- write the final structure proof during the coherent cutover;
- run it only against the re-provisioned final topology.

### F-S4-SEARCH-P2 — incomplete consumer representation audit

The initial manifest missed:

- `tests/process/cli/test_env_layer_boundaries.py`, whose hard-coded
  `_SHIPPED_TOOLS` requires Search to remain a dynamic Tool directory;
- `tests/unit/architecture/test_repo_contracts.py`, whose exact composition
  import set permits only Demand and Task.

These are the same generated/directory/exact-enumeration representation
classes that invalidated the first S3 packet. Treating them as later surprise
failures would repeat D-049's escaped defect.

Correction:

- classify both as writable generic proof consumers;
- repair both from application composition/current source roots, not with a
  Search exception;
- include them in focused and affected proof.

### F-S4-SEARCH-P3 — avoidable double runtime reprovision

The initial sequence moved production Search source, reprovisioned, then moved
Search-owned tests under `src/buddyswitch/modules/search/tests`. D-044 applies
to any `src/buddyswitch/**` mutation, so the sequence required a second
reprovision before testing.

Correction:

- perform production move, module-local test move, consumer corrections and
  current docs as one coherent no-test edit block;
- run `git diff --check`;
- reprovision once after the last package-source mutation;
- invoke the public runner only after activation verifies.

### F-S4-SEARCH-P4 — over-rigid FINAL return policy

The initial packet required every FINAL failure to return to the hub, even
when the failure had one clear owner and every required repair path was already
classified. That would reproduce S2's avoidable coordination loop and conflicts
with the testing contract's bounded `FIX_AFTER_FINAL` state.

Correction:

- run FINAL once per frozen candidate;
- allow at most one owner-correct repair when the cause and every write are
  already classified and no protected boundary changes;
- rerun exact and affected focused proof before one replacement FINAL;
- preserve the failed FINAL as contrary evidence;
- stop immediately for an unclassified, unexplained, environment,
  protected-contract or replacement-FINAL failure.

## 2. Additional preservation evidence

The newly discovered and neighboring direct consumers passed before product
mutation:

```text
run: c50a7fce15e94e0b902f7478abccf6ca
targets:
  tests/process/cli/test_env_layer_boundaries.py
  tests/unit/architecture/test_repo_contracts.py
  tests/unit/daemon/test_decoupling.py
  tests/unit/env_tool/test_schema_contract.py
  tests/integration/runtime/test_tool_feedback.py
result: 55 passed, 17 subtests
duration: 1.22s
cleanup: run root absent; zero instances; Browser inactive
```

Because `_response_case.py` is a shared base class, every current subclass was
also proved before its dead Search/Browser fixture is removed:

```text
run: d0414c37f2a64ca7a1aa0c1c5de1866c
targets: artifact, Demand, registry, Search and Task response suites
result: 29 passed, 18 subtests
duration: 0.25s
cleanup: run root absent; zero instances; Browser inactive
```

## 3. Generic source-root projection preflight

BuddySwitch tests import the activated non-editable distribution. Therefore
`inspect.getmodule(registration.invoke).__file__` points into site-packages and
must not be used as a repository source path.

The generic env-layer proof uses the selected registration's dotted module:

```python
source_dir = (
    REPO_ROOT
    / "src"
    / Path(*registration.invoke.__module__.split(".")).parent
)
```

Read-only preflight on current Demand/Task registrations produced:

```text
demand_sys -> src/buddyswitch/modules/demand/private/adapters/tool
task_sys   -> src/buddyswitch/modules/task/private/adapters/tool
dynamic ∩ explicit: empty
dynamic ∪ explicit: all eight current Tool IDs
result: PASS
```

An initial diagnostic invoked system `python3` and failed before product import
with `ModuleNotFoundError`; it was an operator/interpreter selection error, not
product evidence. The corrected probe used the activated runtime interpreter.
No repository or environment state changed.

## 4. S2/S3 ratchet applied

| Prior lesson | R1 action-time consequence |
|---|---|
| unresolved failure cannot be overwritten | every signal is returned; no blind rerun |
| declared runtime precedes proof | one coherent source block, then reprovision/verify |
| packet contradiction belongs to hub | initial packet rejected before executor time is spent |
| generated/directory consumers count | two omitted consumers are now writable and proved |
| generic proofs must not grow exceptions | derive Tool/source/composition facts generically |
| patch-on-patch is forbidden | a new host/framework is a stop, not an accommodation |
| FINAL is frozen-candidate evidence | one run per frozen candidate; one bounded classified FIX_AFTER_FINAL at most |
| executor must not loop while stopped | one complete return, then stop |

## 5. Determination

The initial packet is rejected and consumed. It must not execute.

The architecture decision remains unchanged: Search is a stateless,
non-opening capability using the existing Tool contribution. Only the
execution proof mode, consumer completeness and reprovision order changed.

`BS-MM-S4-SEARCH-R1-20260730-01` is the sole successor authority.
