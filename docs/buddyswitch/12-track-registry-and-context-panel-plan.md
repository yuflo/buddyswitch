# Track Registry and Context Panel Plan

## Decision

BuddySwitch will use an explicit Track Registry for product iteration state.

The Context Panel should not infer product Tracks from filenames or agent roles. A Track is a user-intended product iteration record that should be traceable toward delivery and acceptance testing.

## Model

- Project: the single physical BuddySwitch workspace.
- Track: an explicit product iteration record in `artifacts/workspace-registry.json`.
- Artifact: a durable agent output under `artifacts/`.
- Untracked Artifact: an artifact not registered to any Track. It is a diagnostic item, not an Inbox.

`Inbox` and `Research Inbox` are intentionally removed from the v1 model for now. They can be revisited later if untracked artifact management becomes a real product need.

## Registry

The registry lives at:

```text
artifacts/workspace-registry.json
```

Minimal schema:

```json
{
  "schema_version": 1,
  "project": {"id": "buddyswitch", "name": "BuddySwitch"},
  "tracks": [
    {
      "id": "onboarding-minimal",
      "title": "Onboarding Minimal",
      "state": "active",
      "artifacts": [
        {"role": "pm", "type": "prd", "path": "artifacts/prd/onboarding-minimal.md"}
      ]
    }
  ]
}
```

`role`, `type`, and `state` are fields. There is no tag system in this version, and no domain labels.

## Context Panel Behavior

- Read `artifacts/workspace-registry.json`.
- Render only registry-declared Tracks in the primary Track list.
- Render files not referenced by any Track as `Untracked Artifacts` diagnostics.
- Do not call agents, LLMs, cleanup, shell commands, or write registry changes from the browser.
- Generate copyable `switch ...` and cleanup commands only.

## Agent Boundary

Track creation and artifact association require explicit user intent.

Agents may suggest registry metadata such as `track_id`, `title`, `role`, `type`, and `state`, but must not create or associate Tracks based only on their own judgment.

## Validation

- `onboarding-minimal` appears as a Track because it is declared in the registry.
- `scheduling-tool-convenience-market-research.md` appears as an Untracked Artifact until the user explicitly registers it.
- Snapshot output includes `tracks`, `untracked_artifacts`, and `summaries`.
- Snapshot output does not include `research_inbox`.
