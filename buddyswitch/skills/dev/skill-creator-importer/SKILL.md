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

## Steps
1. Confirm the target buddy and source package path.
2. Run `python3 scripts/skill_creator_importer.py --source <source> --buddy <buddy>` from the BuddySwitch source checkout, adding `--skill-id <id>` when the intended id must be explicit.
3. Inspect the generated package and `buddyswitch/manifest.toml` diff.
4. Run importer, manifest, runtime materialization, and repo consistency tests.
5. Report the imported skill id, target buddy, package path, manifest registration, and verification output.

## Shared Runtime Rules
- See `framework/docs/skill-runtime-shared-rules.md`.
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.
- Do not introduce transcript parsing, runtime adapter layers, or legacy markdown output paths.

## Required Output Fields
Top-level envelope keys:
- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`
- `artifact_content`

Buddy-specific fields inside `artifact_content`:
- `task_summary`
- `changed_files`
- `implementation_notes`
- `verification`
- `risks`
- `follow_ups`
