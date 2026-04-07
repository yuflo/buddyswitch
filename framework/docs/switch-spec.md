# BuddySwitch v1 Switch Spec

## 1. Scope

This document defines the minimal switch protocol for BuddySwitch v1.

Protocol intent:
- Explicit user-directed routing only
- No automatic task rewrite
- No silent reroute to other agents
- No parallel multi-agent behavior unless user explicitly asks

## 2. Canonical Syntax

```text
switch <agent>: <task>
```

Rules:
- The message must start with `switch`.
- `<agent>` must be one token.
- `:` is required and separates agent from task.
- `<task>` must be non-empty.

## 3. Allowed Agents

Only the following agent names are valid in v1:
- `market`
- `pm`
- `design`
- `dev`
- `test`

## 4. Minimal Parsing Rules

1. Trim leading and trailing whitespace.
2. Check directive prefix:
`switch ...`
3. Parse agent and task using the first `:` as separator.
4. Validate agent against the fixed allowlist.
5. Validate task is non-empty after trimming.
6. On success, return parsed `agent` and `task`.

## 5. Error Handling Rules

When parsing fails:
- Return a clear error.
- Do not guess intent.
- Do not auto-correct agent name.
- Do not re-route to another agent.

Error classes:
- `E_EMPTY_INPUT`: input is empty.
- `E_INVALID_SYNTAX`: not in `switch <agent>: <task>` form.
- `E_UNKNOWN_AGENT`: agent not in allowed list.
- `E_EMPTY_TASK`: task exists syntactically but is empty.

For syntax and unknown-agent errors, include:
- expected syntax: `switch <agent>: <task>`
- one valid example
- list of valid agents (for unknown-agent case)

## 6. Valid Examples

```text
switch pm: Draft an MVP PRD from artifacts/research/live-space.md
switch dev: Implement onboarding flow in projects/app
switch test: Run smoke tests and write report to artifacts/test/onboarding-smoke.md
```

## 7. Invalid Examples

```text
switch potato: do something        # unknown agent
switchpm: do something             # malformed syntax
switch dev do something            # missing ':'
switch design:                     # empty task
```
