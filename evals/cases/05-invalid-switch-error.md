# Case 05: Invalid Switch Rejection

## Intent

Validate that invalid switch directives are rejected clearly with no intent guessing.

## Prompt

```text
switch potato: do something
```

## Preconditions

- `framework/docs/switch-spec.md` exists.
- Minimal parser is available at `scripts/parse_switch.py`.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Optionally verify parser behavior directly:
   - `python3 scripts/parse_switch.py "switch potato: do something"`

## Pass Criteria

- Response returns clear unknown-agent error.
- Valid agents are shown (`market`, `pm`, `design`, `dev`, `test`).
- Expected syntax `switch <agent>: <task>` is shown.
- No silent reroute to another agent.

## Fail Signals

- Agent guess or auto-correction without user confirmation.
- Missing valid-agent guidance.
- Missing syntax guidance.
