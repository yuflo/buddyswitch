# BuddySwitch Interface Spec (Runless)

## Console Data Contract

The context panel reads workspace data from:

- `GET /api/workspace`

Contract source of truth:

- `framework/contracts/workspace-projection.json`

Key projection sections:

- buddies
- tracks
- standalone_tasks
- tasks
- artifacts
- handoffs
- buddybox_files

## Runtime Tool Interface

Runtime operations use broker method `env.tool` with CLI entrypoint:

- `python3 scripts/env/client.py <resource> <operation> ...`

Tool resources:

- `task`
- `track`
- `artifact`
- `handoff`
- `buddybox`
- `context`
- `evidence`
- `search`
