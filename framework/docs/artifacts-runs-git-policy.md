# BuddySwitch Artifacts and Git Policy

## 1. Scope

This document defines where execution outputs go and what should be committed to Git.

Model constraints:
- one workspace repository
- no extra storage system
- no multi-repo split

## 2. Output Boundary

These paths are runtime-workspace-relative. They belong under the launcher-owned execution workspace, not the source checkout.

### `buddyswitch/objects/artifacts/` (canonical artifact outputs)

Task objects group runs and artifact objects. Artifact objects are the source of truth for reusable buddy outputs:
- research reports
- PRDs
- design artifacts
- implementation reports
- test reports

Object source of truth:
- tracks: `buddyswitch/objects/tracks/*.json`
- tasks: `buddyswitch/objects/tasks/*.json`
- artifacts with structured content: `buddyswitch/objects/artifacts/*.json`
- handoff objects: `buddyswitch/objects/handoffs/*.json`
- active buddy private local files: `buddyswitch/local/buddybox/<active-buddy>/**`

### `buddyswitch/local/buddybox/<active-buddy>/` (private local working files)

Use `buddyswitch/local/buddybox/<active-buddy>/` for private local working files that do not fit JSON object fields:
- scratch notes
- transient logs
- debugging traces
- copied snippets and temporary analysis dumps

Do not write temporary runtime noise into `projects/app/` source folders.

## 3. Git Rules

### Commit by default

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/router.toml`
- `buddyswitch/skills/**/SKILL.md`
- `framework/**`
- `projects/app/**`

### Do not commit by default

- generated state under `buddyswitch/objects/**`
- generated buddybox local files under `buddyswitch/local/buddybox/<active-buddy>/**`
- `buddyswitch/local/buddybox/**`
- temporary logs and traces
- scratch dumps
- machine-local clutter
- secret environment files

## 4. Placement Decision Checklist

Ask this before writing output:
1. Will this be useful in future handoff or review?
2. Is this output final enough to cite later?
3. Is this mainly temporary working noise?

Decision:
- If 1 or 2 is yes, write to an artifact object under `buddyswitch/objects/artifacts/`.
- If 3 is yes, write to `buddyswitch/local/buddybox/<active-buddy>/`.
- If content should become product-readable BuddySwitch state, write artifact/handoff objects explicitly; keep private working files in the active buddy local buddybox.
