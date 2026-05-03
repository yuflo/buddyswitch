# BuddySwitch Workspace

BuddySwitch is a control layer for launcher-managed buddy instances.
The host Codex session executes work; BuddySwitch prepares turn context, validates outputs, and persists canonical state.

## Quick Start

Development mode (edit BuddySwitch source):

```bash
codex
```

Product mode (run a locked buddy instance):

```bash
./buddyswitch-codex instance start --buddy pm
```

Then submit an ordinary request, for example:

```text
Draft the MVP PRD for onboarding rewrite
```

## Product Runtime Loop

1. `prepare-turn-context`
2. Codex CLI discovers native runtime skills from `.agents/skills` and runs exactly one selected skill
3. `persist-skill-result`

Runtime CLI:

```bash
python3 scripts/turn_runtime.py prepare "Draft onboarding PRD"
```

```bash
python3 scripts/turn_runtime.py persist \
  --context /tmp/prepare-context.json \
  --skill-id write-prd \
  --result /tmp/result.json
```

Successful `persist` does not reserve a follow-up run.
If another turn is needed, derive next `request_text` from `receipt.next_state`, then run `prepare` again.

## Workspace Layout

Launcher product mode:

- `${BUDDYSWITCH_SHARED_ROOT}` shared launcher root
- `${BUDDYSWITCH_SHARED_ROOT}/state` canonical BuddySwitch state
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` runtime worktree per locked buddy
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` shared product source
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace/.agents/skills` instance-only runtime skills

Canonical state paths:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`
- `runs/raw/` instance-local scratch

## Context Panel

```bash
python3 scripts/serve_context_panel.py
```

Open `http://127.0.0.1:8765/` and click `Refresh workspace`.

## Manage Instances

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy>
./buddyswitch-codex instance list
./buddyswitch-codex instance open <instance-id>
./buddyswitch-codex instance delete <instance-id>
```

## Architecture Docs

- `framework/docs/architecture-overview.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/track-registry.md`
- `framework/docs/interface-spec.md`
