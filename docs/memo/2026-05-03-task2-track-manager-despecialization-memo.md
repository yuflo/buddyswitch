# Task 2: Track-Manager Despecialization Memo

Date: 2026-05-03
Worktree: `dev0210`

## Purpose

Record the agreed scope for Task 2: make `track-manager` a normal PM buddy skill instead of a hard-coded special persistence path.

Task 2 should happen after Task 1 establishes buddy-level result schemas and bridge behavior.

## User Goal

The goal is to stop treating `track-manager` as a special non-artifact skill.

`track-manager` should remain a PM buddy skill, but it should use the same BuddySwitch result abstraction as other PM skills and should no longer require this kind of runtime branch:

```python
if selected_skill_id == "track-manager":
    ...
else:
    ...
```

This is a refactor-forward goal. Backward compatibility with the old non-artifact `track-manager` contract is not required.

## Confirmed Current Behavior

Current `track-manager` differs from other skills:

- Manifest marks it as `produces_artifact = false`.
- It has no `output_slot`.
- It uses `framework/schemas/pm/track-manager.json`.
- Its result contains `track_operation` instead of `artifact_content`.
- `scripts/turn_runtime.py` has a dedicated `_persist_track_manager` path.
- The dedicated path mutates track state and task-track binding.
- The receipt has `artifact_ids = []` and no `artifact_id`.

Current track operations support:

- `create`
- `update`
- `advance`
- `archive`

Current side effects include:

- creating a track;
- updating mutable track fields;
- archiving a track;
- registering the resolved task to a track;
- writing run audit state with `track_action`.

## Confirmed Core Issue

The specialness is not that `track-manager` has a different schema. The specialness is that it performs runtime state effects instead of producing an artifact.

To despecialize it correctly, Task 2 must handle both:

- artifact persistence through the PM buddy-level schema;
- track state effects through a general state-effect mechanism.

Simply changing `track-manager` to `produces_artifact = true` is not enough.

## Target Change

Make `track-manager` a normal PM skill that produces a PM buddy-level result.

Recommended result shape after Task 1:

```json
{
  "execution_summary": "Created onboarding delivery track.",
  "working_notes": [],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "pm_output_type": "track_operation",
    "summary": "Created onboarding delivery track.",
    "decisions": [],
    "risks": [],
    "open_questions": []
  },
  "state_effects": {
    "track_operation": {
      "action": "create",
      "track_id": "track-onboarding-delivery",
      "title": "Onboarding Delivery",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "design",
      "summary": "Cross-functional onboarding delivery flow."
    }
  }
}
```

The exact field names can change during implementation, but the boundary should stay clear:

- `artifact_content` describes the PM-visible artifact.
- `state_effects.track_operation` declares the track mutation to apply.
- `persist` applies state effects through a generic mechanism, not by checking `skill_id == "track-manager"`.

## Scope Included

Task 2 includes:

- Mark `track-manager` as an artifact-producing PM skill.
- Give `track-manager` an output slot under the PM buddy-level artifact model.
- Move track mutation intent into a generic `state_effects.track_operation` contract or equivalent.
- Remove the hard-coded `selected_skill_id == "track-manager"` persist branch.
- Remove manifest/parser/test special casing that currently allows only `track-manager` to use `produces_artifact = false`.
- Preserve explicit PM ownership of track lifecycle changes.
- Ensure track create/update/advance/archive still mutate canonical track/task state correctly.
- Ensure receipts remain useful and include track id/title/action when track state changes.
- Update tests and contracts that currently expect `track-manager` to produce no artifact.

## Scope Excluded

Task 2 does not include:

- Reopening community skill package-format gatekeeping.
- Designing the five buddy-level schemas from scratch; that belongs to Task 1.
- Allowing arbitrary buddies to mutate track lifecycle state.
- Adding hidden or automatic track mutation inference from vague user requests.

## Design Boundary

Track mutation must remain explicit.

`track-manager` can be a normal skill, but track state changes should not become implicit side effects of every PM artifact. The system should apply track effects only when a validated PM result declares a track operation.

Authorization should be based on the validated result contract and active buddy, not on `skill_id == "track-manager"`.

Default boundary for Task 2:

- `state_effects.track_operation` is valid only for active buddy `pm`.
- Non-PM buddies must be rejected before any track/task state write if they submit `state_effects.track_operation`.
- PM results may declare `state_effects.track_operation` only when the user request is explicitly about track lifecycle mutation.
- Skill selection may still route track-lifecycle requests to the `track-manager` skill, but `persist` must not special-case that skill id.

This keeps the product behavior sharp:

- PM still owns track lifecycle.
- Track changes are still auditable.
- The runtime no longer has a skill-id-specific special case.

## Acceptance Criteria

Task 2 is complete when:

- `track-manager` persists through the same artifact path as other PM skills.
- `track-manager` produces a PM artifact and run audit.
- Track create/update/advance/archive still update canonical track/task objects.
- No persist branch depends on `selected_skill_id == "track-manager"`.
- Manifest validation no longer contains a `track-manager`-only exception for non-artifact persistence.
- Negative tests prove non-PM results with `state_effects.track_operation` are rejected before state writes.
- Tests no longer expect `track-manager` receipts to have empty `artifact_ids`.
- Receipts still expose enough track metadata for terminal output and context panel use.

## Working Conclusion

`track-manager` should not remain a special non-artifact runtime path.

It should become a normal PM buddy skill whose result may include a validated track state effect. This keeps BuddySwitch aligned with the buddy-level bridge model while preserving explicit PM control over track lifecycle.
