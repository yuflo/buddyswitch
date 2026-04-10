# BuddySwitch Skill Architecture Best Practices

## Current Target

BuddySwitch is a host-CLI orchestration framework, not a standalone agent runtime and not a native Codex skill pack.

That means:

- Codex CLI provides the general-agent runtime.
- BuddySwitch owns protocol, authority, state, and persistence.
- BuddySwitch skills stay under `buddyswitch/skills/**/SKILL.md`.
- The host Codex session chooses the skill from BuddySwitch-provided candidates.
- BuddySwitch scripts never call a second LLM backend to route skills.

## Why This Matches Best Practice

Across current coding-agent ecosystems, the common pattern is:

1. keep workflow bundles in skill-like packages
2. expose compact metadata first
3. let the host agent choose when to use a workflow
4. keep deterministic validation and state mutation outside the model

BuddySwitch follows that pattern, but keeps one extra control layer:

- user chooses the buddy explicitly with `switch <buddy>: <task>`
- BuddySwitch constrains the host model to that buddy's allowlisted skill set

## Layer Responsibilities

### Host Codex

- interpret the current user task
- choose one `skill_id` from `eligible_skills`
- read the selected `buddyswitch/skills/.../SKILL.md`
- execute the workflow
- emit structured output matching the chosen schema

### BuddySwitch

- parse `switch <buddy>: <task>`
- load manifest, buddy scope, permissions, and allowed skills
- apply deterministic eligibility gates
- resolve track context and default paths
- validate structured outputs at persistence time
- write track/artifact state and compatibility markdown files

## Canonical Flow

1. `parse`
2. `resolve`
3. `run`
4. `persist`

`parse`, `resolve`, and `persist` are BuddySwitch primitives.
`run` is performed by the host Codex session.

## Skill Contract

Each BuddySwitch skill should contain:

Required front matter:

- `name`
- `description`
- `track_mode`
- `default_artifact_kind`
- `auto_summary`
- `output_schema`

Recommended front matter:

- `version`
- `side_effect_level`
- `required_tools`
- `required_env`
- `produces`
- `consumes`

Required body sections:

- `Purpose`
- `Use when`
- `Do not use when`
- `Inputs`
- `Outputs`
- `Verification`
- `Examples`
- `Counterexamples`
- `Gotchas`

## Output Contract

The host Codex session should not improvise persistence structure.

Instead:

- `resolve` reports `required_output_schema_by_skill`
- the host emits a structured payload that matches that schema
- `persist` writes canonical JSON to `buddyswitch/content/**`
- BuddySwitch renders markdown compatibility files for the current panel

This keeps structured state canonical while preserving the current human-readable workflow.

## Deliberate Non-Goals

BuddySwitch does not do these things in the production path:

- internal semantic routing via OpenAI API or any second backend
- trigger-first compatibility routing as the default
- native Codex `.agents/skills` discovery for BuddySwitch-owned skills
- business-quality review during persistence

## Why Persist Stays Thin

`persist` is not a review stage.

It is a lightweight technical gate for:

- selected skill identity
- schema conformance
- object authority
- state/reference sanity

Business quality stays in the host agent flow and the next buddy handoff, not in BuddySwitch persistence.
