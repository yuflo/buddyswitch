# Case 05: Invalid Switch Rejection (Manifest-Backed)

## Intent

Validate that invalid switch directives are rejected clearly and buddy validation comes from manifest.

## Prompt

```text
switch potato: do something
```

## Preconditions

- `framework/docs/switch-spec.md` exists.
- Parser exists at `scripts/parse_switch.py`.
- Manifest exists at `buddyswitch/manifest.toml`.

## Manual Steps

1. Run:
   - `python3 scripts/parse_switch.py "switch potato: do something"`
2. Confirm `valid_agents` list is derived from manifest entries.

## Pass Criteria

- Unknown-buddy error is explicit.
- Expected syntax `switch <buddy>: <task>` is shown.
- Current valid buddies from manifest are shown.
- No silent reroute.

## Fail Signals

- Hardcoded buddy list mismatch with manifest.
- Agent guess or auto-correction without user confirmation.
