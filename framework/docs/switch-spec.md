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

## Runtime Resolution

- Resolve/execute entry: `scripts/switch_runtime.py`.
- Resolution order:
  1. parse switch
  2. select buddy skill from `SKILL.md` front matter (`triggers` then `default`)
  3. resolve track context from `track_mode`
  4. derive default artifact/summary paths when needed

Skill selection rules for a multi-skill buddy:

- first trigger hit wins
- if no trigger hit, use the single skill marked `default: true`
- if still ambiguous, return explicit conflict error

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
- Runtime resolve: `python3 scripts/switch_runtime.py resolve "switch pm: continue track"`
- Runtime execute: `python3 scripts/switch_runtime.py execute "switch market: quick market research for AI scheduler"`
