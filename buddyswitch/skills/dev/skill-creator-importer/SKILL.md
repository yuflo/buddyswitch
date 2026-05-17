---
name: skill-creator-importer
description: Use when importing an external Codex-native skill package into BuddySwitch source and registering it for a target buddy.
---

# skill-creator-importer

## Purpose
- Import one external Codex-native skill package into BuddySwitch source as a repo-registered skill.

## Use when
- The user provides or references an external Codex skill package or `SKILL.md`.
- The user wants the skill available to one BuddySwitch buddy: `pm`, `dev`, `test`, `market`, or `design`.
- The task is about registering the skill for future normal runtime materialization.

## Do Not Use When
- The request asks to hot-reload an already-running Codex session.
- The request asks to parse Codex transcripts or adapt arbitrary community output through runtime adapters.
- The request asks to build a marketplace, sync daemon, package registry, or runtime adapter.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable skill import report content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Steps
1. Confirm the target buddy and source package path.
2. Run `python3 scripts/skill_creator_importer.py --source <source> --buddy <buddy>` from the BuddySwitch source checkout, adding `--skill-id <id>` when the intended id must be explicit.
3. Inspect the generated package and `buddyswitch/manifest.toml` diff.
4. Run importer, manifest, runtime materialization, and repo consistency tests.
5. Report the imported skill id, target buddy, package path, manifest registration, and verification output.

## Shared Runtime Rules

- Runtime execution uses env.tool through python3 scripts/env/client.py ... .
- Product-readable durable state is written explicitly as task or artifact objects.
- Use buddybox env tools with `logical_name` for active-buddy-private working files.
- Return after required explicit durable writes are complete.
- Do not introduce transcript parsing, runtime adapter layers, or legacy markdown output paths.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `kind`: `skill-import-report`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `task_summary`, `changed_files`, `implementation_notes`, `verification`, `risks`, and `follow_ups`

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
