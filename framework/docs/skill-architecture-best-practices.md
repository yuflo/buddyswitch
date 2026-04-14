# BuddySwitch Skill Architecture Best Practices

## Current Target

BuddySwitch is a host-CLI orchestration framework, not a standalone agent runtime and not a native Codex skill pack.

That means:

- Codex CLI provides the general-agent runtime.
- BuddySwitch owns protocol, authority, state, and persistence.
- BuddySwitch skills are skill packages under `buddyswitch/skills/**/` with `skill.toml` + `SKILL.md`.
- The host Codex session chooses the skill from BuddySwitch-provided candidates.
- BuddySwitch scripts never call a second LLM backend to route skills.

## Why This Matches Best Practice

Across current coding-agent ecosystems, the common pattern is:

1. keep workflow bundles in skill-like packages
2. expose compact metadata first
3. let the host agent choose when to use a workflow
4. keep deterministic validation and state mutation outside the model

BuddySwitch follows that pattern, but keeps one extra control layer:

- user chooses the buddy explicitly with `switch <buddy>...: <demand>`
- BuddySwitch treats the text after `:` as demand text; task objects are resolved or created by the runtime
- BuddySwitch constrains the host model to that buddy's allowlisted skill set while keeping invocation parsing tolerant to minor CLI formatting variation

## Layer Responsibilities

### Host Codex

- interpret the current user task
- choose one `skill_id` from `eligible_skills`
- read the selected skill package instruction file `buddyswitch/skills/.../SKILL.md`
- execute the workflow
- emit structured output matching the chosen schema

### BuddySwitch

- parse supported `switch <buddy>...: <demand>` forms
- load manifest, buddy scope, object authority metadata, and allowed skills
- apply only the deterministic gates needed for safe resolution
- resolve task context, optional track context, and reject retired markdown output requests
- validate structured outputs at persistence time
- write task/artifact/track state and run audit payloads

In this model:

- `buddy -> skills` is the main runtime routing authority
- `permissions` are object-authority metadata for manual/debug mutation APIs
- `required_tools` and `required_env` are advisory metadata for the host session, not resolve gates

## Canonical Flow

1. `parse`
2. `resolve`
3. `run`
4. `persist`

`parse`, `resolve`, and `persist` are BuddySwitch primitives.
`run` is performed by the host Codex session.

## Skill Contract

Each BuddySwitch skill package should contain:

Required metadata in `skill.toml`:

- `id`
- `buddy`
- `description`
- `objects`
- `produces_artifact`
- `input_slots`
- `output_schema`

Conditional metadata in `skill.toml`:

- `output_slot` (required when `produces_artifact=true`)

Recommended metadata in `skill.toml`:

- `side_effect_level`
- `required_tools`
- `required_env`
- `produces`
- `consumes`
- `allowed_task_kinds`

`required_tools` and `required_env` stay host-facing advisory metadata. They are not resolve reject gates.

The top-level env manifest keeps only `id` and `path` for each `[[skills]]` entry. BuddySwitch loads the package metadata from `skill.toml` and uses it as the authoritative source for skill descriptions, object coverage, and runtime buddy identity.

Routing is validated by checking that the `buddy` declared in `skill.toml` is present in the matching `[[buddies]]` entry's `skills` list. The manifest no longer duplicates skill descriptions or object lists.

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
- `persist` creates or reuses the resolved task for the run
- `persist` writes canonical artifact content into artifact objects
- `persist` writes run audit JSON to `buddyswitch/content/runs/**`
- BuddySwitch does not maintain a derived markdown compatibility layer

This keeps structured state canonical and removes duplicated runtime outputs.

`output_schema.py` is a structure validator only. It may reject malformed payloads, unsupported fields, or invalid enum/type combinations, but it must not become a business-quality or workflow-quality review layer.

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
- state/reference sanity

Business quality stays in the host agent flow and the next buddy handoff, not in BuddySwitch persistence.
