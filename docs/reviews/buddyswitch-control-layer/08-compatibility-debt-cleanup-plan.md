# 08. Compatibility Debt Cleanup Status

## 1. Position

This note is now a historical status page. Phase 2C is the active model and is implemented.

Current BuddySwitch runtime state is canonicalized to:

- artifact objects: `buddyswitch/objects/artifacts/*.json`
- track objects: `buddyswitch/objects/tracks/*.json`
- run audit content: `buddyswitch/content/runs/*.json`

Derived markdown compatibility outputs under `artifacts/*.md` and `runs/summaries/**` are retired from runtime ownership.

## 2. Phase 2C Closure

The following changes are complete:

- Runtime `persist` writes object store plus run audit only.
- Runtime rejects explicit legacy markdown output requests in switch task text.
- Artifact object schema no longer carries `path` or `summary_path`.
- Workspace API no longer returns `untracked_artifacts` or `summaries`; it returns `run_audits`.
- Context panel no longer renders artifact inbox or run summaries.
- Cleanup no longer manages markdown artifact/summary categories as BuddySwitch state.

## 3. Validation Snapshot

Acceptance checks are aligned with the Phase 2C direct convergence plan:

- `python3 -m unittest discover -s tests`
- `python3 -m py_compile scripts/*.py`
- `git diff --check`

## 4. Relationship To 09

`09-phase-2c-direct-convergence-plan.md` is the authoritative implementation plan.
This file remains as an audit-trail status marker only.

