# S3 Task Current-Guidance Repair Acceptance

> Origin: S7 R1 Replacement audit
> Scope: root README plus one Task-owned architecture regression
> Decision: `ACCEPTED`

## Acceptance sentence

Root/current guidance names the current `task_sys` Tool and canonical Task
object path, and a Task-boundary architecture test rejects the retired
`task.*` and `taskbox` guidance.

## Root cause and repair

S3's original replacement proof covered Task code, Skills, architecture docs
and retired physical roots but omitted root `README.md` semantics. S7 R1
therefore found a real guidance contradiction even though all executable tests
passed.

The bounded forward repair:

- changes `task.*` to `task_sys.*`;
- replaces the two retired per-instance taskbox paths with
  `buddyswitch/objects/task-sys/tasks/*.json`;
- adds one direct current-guidance assertion to the existing Task architecture
  proof owner; it is not a new documentation scanner or policy framework.

No product source, runtime contract, state, package or behavior changed.

## Evidence

```text
repair patch: a106d869b342910f718231263f732d6e84f260d09cc590a2b002a053a0b05ebc

RED:
./buddyswitch-test focused \
  tests/unit/architecture/test_task_sys_boundaries.py::test_current_guidance_names_task_sys_tool_and_canonical_state_only
run 5cb7ecb2954a416e85e44d7d276c9d56
1 failed for missing current task_sys guidance

exact GREEN:
same command
run 90a672c1176049428c05db2faa3d8b4f
1 passed

affected GREEN:
./buddyswitch-test focused \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/architecture/test_package_contract.py
run 71208e299dc541a092fc4b54f4588170
33 passed, 26 subtests passed
```

Every runner root was removed. No attributable process, socket, lock or temp
state remained. Runtime reprovision is inapplicable because `src/**` and every
runtime input are unchanged.

## Closure

The Task portion of `R-DOC-002` is closed again on the new enforceable proof.
The executable S3 architecture remains accepted. S7 R1 remains rejected and
consumed; only a new committed S7 packet may restart final acceptance.
