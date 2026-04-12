# Case 10: Resolve Returns Skill Candidates Without Auto-Selection

## Intent

Validate that BuddySwitch `resolve` constrains the host agent to the current buddy's eligible skills and does not auto-select for a multi-skill buddy.

## Prompt

```text
switch pm: continue track-demo track and define the MVP scope with acceptance criteria
```

## Preconditions

- `track-demo` exists and is active.
- `scripts/switch_runtime.py` is the current runtime entry.

## Manual Steps

1. Run:
   - `python3 scripts/switch_runtime.py resolve "switch pm: continue track-demo track and define the MVP scope with acceptance criteria"`
2. Inspect the JSON output.
3. Confirm that the host now has enough candidate metadata and schema info to choose the skill in-session.

## Pass Criteria

- `eligible_skills` includes both `write-prd` and `track-manager`.
- `implicit_skill_id` is `null`.
- `skill_cards` includes compact routing guidance for both candidates.
- `required_output_schema_by_skill` includes both schema paths.
- `artifact_defaults_by_skill.write-prd` exists.
- `resolve` does not return markdown summary defaults.

## Fail Signals

- The runtime auto-selects one PM skill when multiple candidates remain eligible.
- The runtime requires an API key or internal model backend to complete `resolve`.
- The result does not give the host enough metadata to choose a skill and continue.
