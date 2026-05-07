# BuddySwitch Historical Residue Cleanup Audit Memo

## Goal

Record the current cleanup audit after the buddy instance environment tool layer
iteration.

This memo is not about one PM or Market case. It is a cleanup map for removing
historical code and documentation residue that no longer serves the current
BuddySwitch direction.

## Correct Direction

The recent iteration target was the first correct step for buddy instances:

```text
更多的上下文、工具的权限
```

More precisely, the direction is:

1. Make execution boundaries real through env profiles, sandbox roots, runtime
   broker, browser evidence gate, active-buddy skills, and runtime AGENTS
   projection.
2. Make product-mode `prepare` / `persist` the controlled main path for state
   mutation.
3. Then productize context projection and tool semantic feedback so buddies do
   not need to inspect source code or schemas to infer the correct path.

The goal is not to patch prompts for one observed test case.

## Audit Standard

The cleanup question is:

```text
Does this code or doc still help the current buddy env/tool-layer direction,
or does it drag the system back toward old runtime models?
```

The highest-priority cleanup targets are not old archived specs by themselves.
The highest-priority targets are active runtime code, active contracts, active
skill docs, active templates, and active tests that still teach or enforce the
wrong model.

## Summary

The current runtime main path is mostly on the new model:

- buddy-run persist
- broker-controlled product-mode prepare/persist
- env-profile capability boundaries
- browser evidence gate
- active-buddy-only runtime skills

The remaining residue is concentrated in four active groups:

1. old switch-shaped request rejection
2. old result authoring contract (`artifact_content`, `deliverables_or_changed_files`)
3. remaining `track_operation` schema/test residue
4. store and repository wrapper residue still labeled `legacy`

There are also smaller wording and compatibility leftovers in active docs and
helper modules.

## Group 1: Switch Command Runtime Residue

This group directly conflicts with the current rule that the active buddy comes
only from locked instance metadata, not from user text.

### Why It Is Wrong Now

Text such as:

```text
switch market: do competitor scan
```

should now be treated as ordinary `request_text` inside the current locked
buddy.

Rejecting it keeps an old router-era behavior alive inside the runtime.

### Active Residue

- `scripts/turn_runtime.py::_is_legacy_command_shaped_request`
- `scripts/turn_runtime.py` prepare branch returning `E_LEGACY_COMMAND_INPUT`
- `tests/test_turn_runtime.py::test_prepare_rejects_legacy_command_shaped_request_without_reservation`
- `docs/spec/2026-05-06-buddy-run-persist-test-plan.md` still says legacy
  command-shaped requests remain rejected

### Evidence

- `scripts/turn_runtime.py:331`
- `scripts/turn_runtime.py:946`
- `tests/test_turn_runtime.py:211`
- `docs/spec/2026-05-06-buddy-run-persist-test-plan.md:227`

### Cleanup Decision

Remove this runtime rejection path.

The launcher may still fail closed on retired top-level CLI commands, but the
runtime should no longer reject switch-prefixed ordinary text.

## Group 2: Old Result Authoring Contract Still Drives Active Skills

This is the largest remaining source of behavioral drift.

The runtime persist main path now accepts a compact buddy-run commit:

- `execution_summary`
- optional `working_notes`
- optional `artifacts`
- optional `state_effects`
- optional `handoff`
- optional `contributors`
- optional `tool_evidence`

However, many active contracts, skills, templates, and tests still teach the
old result shape:

- `deliverables_or_changed_files`
- `artifact_content`
- `specialized_sections`

### Why It Matters

This mismatch forces buddies to reconcile two mental models:

1. skill/contracts/schema authoring model
2. runtime persist commit model

That is one direct reason why PM logs showed source reading and schema
inspection instead of a short canonical execution recipe.

### Active Residue Surface

The old authoring contract is still present in at least these active files:

- all 5 buddy result schemas under `framework/schemas/`
- 12 active `SKILL.md` files under `buddyswitch/skills/`
- 13 active skill template assets under `buddyswitch/skills/**/assets/`
- 2 active buddy contracts
- 1 active schema-boundary test file

### Concrete Active Files

Contracts:

- `framework/contracts/pm.md`
- `framework/contracts/market.md`

Schemas:

- `framework/schemas/pm/pm-result.json`
- `framework/schemas/market/market-result.json`
- `framework/schemas/design/design-result.json`
- `framework/schemas/dev/dev-result.json`
- `framework/schemas/test/test-result.json`

Example skills:

- `buddyswitch/skills/pm/write-prd/SKILL.md`
- `buddyswitch/skills/pm/track-manager/SKILL.md`
- `buddyswitch/skills/market/research-scan/SKILL.md`
- `buddyswitch/skills/design/shape-prototype/SKILL.md`
- `buddyswitch/skills/dev/implement-task/SKILL.md`
- `buddyswitch/skills/test/smoke-test/SKILL.md`

Example templates:

- `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`
- `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
- `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
- `buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md`
- `buddyswitch/skills/test/smoke-test/assets/test-report-template.md`

Test:

- `tests/test_output_schema_boundaries.py`

### Evidence

- `framework/contracts/pm.md:12`
- `framework/contracts/pm.md:30`
- `buddyswitch/skills/pm/write-prd/SKILL.md:27`
- `buddyswitch/skills/pm/write-prd/SKILL.md:46`
- `framework/schemas/pm/pm-result.json:3`
- `tests/test_output_schema_boundaries.py:300`

### Cleanup Decision

This is not archival residue. It is active product-path residue and should be
reworked.

The system should converge on one compact buddy-run authoring model that matches
runtime persist, instead of keeping a separate old structured authoring contract
as the dominant guidance surface.

## Group 3: `track_operation` Residue

The runtime main path has already moved to:

- `state_effects.track`

But a small active residue still preserves:

- `state_effects.track_operation`

### Why It Is Wrong Now

This preserves the retired PM track mutation shape in schemas and tests even
though runtime behavior has moved on.

### Active Residue

- `framework/schemas/pm/pm-result.json`
- `tests/test_output_schema_boundaries.py`

There are also references in old specs and investigation memos, but those are
not the primary problem. The live schema/test pair is the part that still
matters.

### Evidence

- `framework/schemas/pm/pm-result.json:50`
- `tests/test_output_schema_boundaries.py:308`

### Cleanup Decision

Replace the remaining active `track_operation` authoring residue with the
current `state_effects.track` shape.

## Group 4: Store And Repository Legacy Wrapper Residue

The current object store is still described internally as legacy.

### Why It Matters

This is not the most user-visible bug, but it keeps the implementation in a
confused structural state:

- current canonical store functions are named `_legacy_*`
- `runtime_store/repositories.py` is a wrapper layer that delegates back to
  `env_store._legacy_*`
- tests explicitly assert delegation to `_legacy_*`

This makes the active implementation look like a temporary bridge even when it
is the real store.

### Active Residue

- `scripts/env_store.py` defines 26 `_legacy_*` functions that are actually the
  current implementation
- `scripts/runtime_store/repositories.py` delegates all repository entrypoints
  to those `_legacy_*` functions
- `tests/test_env_store_v2.py` asserts those `_legacy_*` delegations

### Evidence

- `scripts/runtime_store/repositories.py:1`
- `scripts/runtime_store/repositories.py:9`
- `scripts/env_store.py:349`
- `scripts/env_store.py:487`
- `tests/test_env_store_v2.py:34`

### Cleanup Decision

Flatten this layer.

The active store should stop calling its own canonical implementation
`legacy`, and unnecessary pass-through wrappers should be removed or renamed so
the code matches the actual architecture.

## Group 5: Smaller Active Wording And Compatibility Residue

These are not the main blocker, but they continue to blur the model.

### Examples

- `framework/docs/browser-cockpit.md` still says the host executes
  `selected skill` work locally
- `scripts/env_manifest.py` still keeps a compatibility comment for older
  turn-runtime imports

### Evidence

- `framework/docs/browser-cockpit.md:20`
- `scripts/env_manifest.py:28`

### Cleanup Decision

Clean these opportunistically while touching the surrounding files.

## Debug API Status

Manual object APIs still exist:

- `scripts/env_tracks.py`
- `scripts/env_artifacts.py`
- `scripts/env_tasks.py`

These are not currently the highest-priority runtime bug, because active docs
already mark them as manual/debug APIs rather than the product runtime path.

However, they remain a side-path family and should be evaluated after the four
main groups above.

The likely direction is:

- keep only if clearly needed for admin/debug maintenance
- otherwise demote further or remove

## What Is Not The Primary Cleanup Target

Not every old document is equally urgent.

Lower-priority residue includes:

- archived development plans in `docs/spec/2026-05-05-*`
- investigation memos that intentionally describe historical behavior
- launcher tests that deliberately prove old public CLI commands fail closed
- references to old shared workspace migration guards

These may be cleaned later, but they are not the first blockers for buddy
behavior convergence.

## Priority Order

### Batch 1

Remove switch-shaped runtime rejection.

Why first:

- small scope
- directly conflicts with locked-buddy authority
- already has a dedicated cleanup memo and clear acceptance criteria

### Batch 2

Unify active contracts, skills, templates, and guidance around the compact
buddy-run payload.

Why second:

- this is the biggest current source of model confusion
- it directly affects PM, Market, Design, Dev, and Test behavior
- it is the main reason buddies still need to inspect source/schema details

### Batch 3

Remove remaining active `track_operation` schema/test residue.

Why third:

- tightly related to Batch 2
- smaller than the full authoring-contract cleanup
- keeps PM track lifecycle shape consistent

### Batch 4

Flatten `runtime_store` and remove `_legacy_*` naming and wrapper residue.

Why fourth:

- less immediately visible to the buddy than Batch 1 and Batch 2
- still important for architectural clarity and future iteration speed

## Estimated Active Residue Size

If counting only active code, active contracts, active skills, active templates,
active tests, and active runtime docs that still conflict with the current
direction, the cleanup surface is roughly:

- about 40 active files requiring change or review

This count excludes archived specs whose main value is historical record.

## Conclusion

The environment tool layer iteration did the first correct thing: it moved the
runtime toward enforced capability boundaries.

The next cleanup bottleneck is not another one-off permission patch. It is the
removal of active historical residue that still teaches or enforces the wrong
runtime model.

The most important principle for cleanup is:

```text
Do not preserve parallel runtime mental models.
```

BuddySwitch should expose one clear product path:

- locked buddy identity from instance metadata
- env-profile capability boundary
- broker-controlled prepare/persist
- compact buddy-run commit payload
- durable track/artifact/handoff continuity

