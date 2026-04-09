# BuddySwitch Switch Spec

## Canonical Syntax

```text
switch <buddy>: <task>
```

Rules:

1. Message must start with `switch`.
2. `<buddy>` must be one token.
3. `:` is required.
4. `<task>` must be non-empty.

## Buddy Validation

- Buddy names are loaded from `buddyswitch/manifest.toml`.
- Do not use a hardcoded allowlist in parser or router.

## Error Handling

Parsing should return explicit errors:

- `E_EMPTY_INPUT`
- `E_INVALID_SYNTAX`
- `E_UNKNOWN_AGENT`
- `E_EMPTY_TASK`
- `E_ENV_MANIFEST`

For syntax and unknown-buddy errors include:

- expected syntax: `switch <buddy>: <task>`
- one valid example
- current valid buddies from manifest

## Reference Commands

- Parser: `python3 scripts/parse_switch.py "switch pm: continue track"`
- Router: `python3 scripts/codex_router.py "switch pm: continue track"`
