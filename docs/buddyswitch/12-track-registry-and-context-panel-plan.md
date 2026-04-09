# Track Registry and Context Panel Plan

## Decision

BuddySwitch will use an explicit Track Registry for product iteration state.

The Context Panel should not infer product Tracks from filenames or agent roles. A Track is a user-intended product iteration record that should be traceable toward delivery and acceptance testing.

## Model

- Project: the single physical BuddySwitch workspace.
- Track: an explicit product iteration record managed through `scripts/registry.py` and currently dumped to `artifacts/workspace-registry.json`.
- Artifact: a durable agent output under `artifacts/`.
- Untracked Artifact: an artifact not registered to any Track. It is a diagnostic item, not an Inbox.

`Inbox` and `Research Inbox` are intentionally removed from the v1 model for now. They can be revisited later if untracked artifact management becomes a real product need.

## Registry

The v1 local dump backend lives at:

```text
artifacts/workspace-registry.json
```

Registry writes should go through:

```text
scripts/registry.py
```

This adapter is not the final storage architecture. It preserves the operation model that can later move to a database or standard storage API.

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

- Read live workspace data from the local Context Panel server.
- Render only registry-declared Tracks in the primary Track list.
- Render files not referenced by any Track as `Artifact Inbox` diagnostics.
- Do not call agents, LLMs, cleanup, shell commands, or write registry changes from the browser.
- Generate copyable `switch ...` and cleanup commands only.
- Use the local Context Panel server for active refresh.

## Agent Boundary

Track creation and artifact association require explicit user intent.

Agents may suggest registry metadata such as `track_id`, `title`, `role`, `type`, and `state`, but must not create or associate Tracks based only on their own judgment. When explicit Track intent is present, agents should use `scripts/registry.py` rather than editing JSON directly.

## Validation

- `onboarding-minimal` appears as a Track because it is declared in the registry.
- `scheduling-tool-convenience-market-research.md` appears in Artifact Inbox until the user explicitly registers it.
- Workspace data includes `tracks`, `untracked_artifacts`, and `summaries`.
- Workspace data does not include `research_inbox`.
