# BuddySwitch Skill Creator Importer Memo

Date: 2026-05-03
Worktree: `dev0210`
Status: Historical memo; superseded by 2026-05-05 runtime gate trimming boundary docs for runtime validation behavior.

## Purpose

Record the agreed target for a BuddySwitch creator skill that imports non-BuddySwitch Codex skills into this repo.

This memo covers only the creation/import/registration process. It does not cover live synchronization into already-created buddy instances.

## User Goal

The goal is to make a non-BuddySwitch Codex `SKILL.md` usable by future BuddySwitch buddy instances.

The creator skill should:

1. Accept an external/community Codex skill as input.
2. Accept a target BuddySwitch buddy/template: `pm`, `dev`, `test`, `market`, or `design`.
3. Generate a repo-registered Codex-native skill package with BuddySwitch persist guidance under the repo.
4. Register that generated skill in `buddyswitch/manifest.toml`.
5. Make the skill available to newly created buddy instances for the selected buddy.

## Confirmed Current Runtime Path

BuddySwitch currently materializes runtime skills during instance workspace preparation:

```text
buddyswitch/manifest.toml
-> current buddy's skills list
-> each skill's manifest path
-> copy package into instance workspace .agents/skills/<skill-id>
-> Codex CLI discovers and executes from .agents/skills
```

Current code path:

- `tools/launcher/workspace.sh` calls `scripts/runtime_skills.py install --buddy <buddy> --workspace <workspace>`.
- `scripts/runtime_skills.py` reads the selected buddy's skill ids from manifest.
- Each skill id resolves to a manifest `path`.
- The package at that path is copied into runtime `.agents/skills/<skill-id>`.

Therefore a generated skill becomes available to an instance only if it exists in the repo and is registered in manifest before that instance workspace is prepared.

## Target Creator Behavior

The creator skill should copy an external Codex-native skill package into the BuddySwitch repo and add BuddySwitch persist closing rules:

```text
external/community SKILL.md
-> BuddySwitch creator skill
-> buddyswitch/skills/<buddy>/<new-skill-id>/SKILL.md
-> buddyswitch/manifest.toml updated
```

The generated package should preserve the original skill's useful workflow while adding BuddySwitch runtime closing rules such as:

- use the selected buddy-level result template;
- produce output in a shape `persist` can safely write;
- keep native Codex execution from `.agents/skills`;
- identify the generated skill by its registered `skill_id`.

## Template Boundary

The creator skill should require the target template/buddy to be explicit.

Allowed target templates:

- `pm`
- `dev`
- `test`
- `market`
- `design`

After Task 1, these should map to the five buddy-level result templates. The creator should not generate a new skill-specific schema for every imported community skill by default.

## Registration Boundary

The creator skill should update the repo registration needed for future instance materialization:

- Add a `[[skills]]` manifest entry.
- Set `id` to the generated skill id.
- Set `path` to `buddyswitch/skills/<buddy>/<skill-id>`.
- Set artifact persistence fields according to the selected buddy-level template.
- Add the skill id to the selected `[[buddies]]` skill list.

The exact output slot convention can be decided during implementation, but it should be deterministic and not require manual editing after generation.

## Explicit Non-Goals

This task does not include:

- hot syncing the generated skill into already-created buddy instances;
- auto-reloading `.agents/skills` inside active instances;
- parsing Codex CLI transcripts or final responses;
- replacing Task 1 buddy-level result templates;
- replacing Task 2 `track-manager` despecialization;
- reopening runtime package validation gates, which are already closed by the 2026-05-05 runtime gate trimming boundary;
- adapting arbitrary community output through a runtime bridge, wrapper, transcript parser, or legacy conversion path.

## Instance Synchronization Boundary

Existing instances are out of scope.

An imported skill appears in runtime `.agents/skills` after an instance workspace is created or explicitly refreshed by the existing launcher open/sync/start materialization path. Already-running Codex sessions are not hot-reloaded by this task.

This separation is intentional for this task. Creator output changes repo state; instance synchronization is a separate lifecycle concern.

## Acceptance Criteria

This task is complete when:

- A non-BuddySwitch Codex skill can be copied into a generated package under `buddyswitch/skills/<buddy>/<skill-id>/`.
- The generated package contains a valid `SKILL.md` with the original workflow preserved and BuddySwitch persist closing rules added.
- `buddyswitch/manifest.toml` registers the generated skill and attaches it to the selected buddy.
- A newly created buddy instance for that buddy materializes the generated skill into `.agents/skills/<skill-id>`.
- The generated skill can be selected and run by Codex CLI in that new instance and can reach the BuddySwitch persist path expected for the selected template.

## Working Conclusion

The creator skill is a direct import-and-registration path for external Codex-native skills.

```text
do not parse Codex sessions after the fact
instead generate a repo-registered Codex-native skill with BuddySwitch persist guidance before instance creation
```

The intended result is clear: external Codex skills become repo-registered BuddySwitch skills that future buddy instances can copy and execute effectively.
