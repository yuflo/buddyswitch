# BuddySwitch Skill Package V2

## Status

- Date: 2026-04-14
- Status: Draft
- Scope: skill package structure and metadata contract for BuddySwitch v2

## 1. Goal

BuddySwitch v2 replaces the current single-file skill contract with a package contract.

This change is needed because BuddySwitch is no longer at the stage where one `SKILL.md` can responsibly carry:

- routing metadata
- workflow instructions
- template references
- examples
- scripts
- validation hints

The new package contract splits machine-readable metadata from human-readable instructions.

## 2. Problems In The Current Model

The current model relies on:

- `manifest.toml` pointing to `SKILL.md`
- front matter inside `SKILL.md`
- guidance headings inside `SKILL.md`

This creates several scaling problems:

- metadata and instructions are mixed
- referenced templates may not actually exist
- richer package resources are not first-class
- routing between adjacent skills depends too much on prose descriptions

## 3. Core Decision

Each BuddySwitch skill becomes a package directory with a dedicated metadata file.

Recommended structure:

```text
buddyswitch/skills/<buddy>/<skill>/
  skill.toml
  SKILL.md
  references/
  examples/
  assets/
  scripts/
  evals/
```

The exact subdirectories may start empty, but the package shape is now the contract.

## 4. File Roles

## 4.1 `skill.toml`

`skill.toml` is the machine-readable contract.

Recommended fields:

- `id`
- `buddy`
- `description`
- `produces_artifact`
- `output_slot`
- `input_slots`
- `output_schema`
- `produces`
- `consumes`
- `side_effect_level`
- `required_tools`
- `required_env`
- `allowed_task_kinds`

Future metadata may also include:

- routing hints
- workflow flags
- eval set references

This file is what runtime should parse for routing and contract assembly.

Rules:

1. `produces_artifact = true` requires a non-empty `output_slot`.
2. `produces_artifact = false` must omit `output_slot`.
3. `input_slots` may be empty.

## 4.2 `SKILL.md`

`SKILL.md` becomes the execution guidance for the host session.

It should describe:

- purpose
- when to use
- when not to use
- workflow steps inside the skill boundary
- output expectations
- verification expectations
- links to package resources

It should not be the only home of machine-readable runtime metadata.

## 4.3 `references/`

Use for:

- domain rules
- deeper process notes
- edge-case guidance

## 4.4 `examples/`

Use for:

- input examples
- output examples
- good and bad cases

## 4.5 `assets/`

Use for:

- templates
- report skeletons
- reusable static text resources

If `SKILL.md` says “use the template”, the template must exist in `assets/`.

## 4.6 `scripts/`

Use for:

- validators
- helper extractors
- repetitive package-local automation

## 4.7 `evals/`

Use for:

- package-local eval inputs
- expected outputs
- rubric fragments

## 5. Manifest Changes

Buddy manifest should stop treating `SKILL.md` as the canonical package entry.

Preferred direction:

- manifest points to skill package root or `skill.toml`

Runtime can still expose `SKILL.md` as the host-readable instruction file, but manifest authority should not depend on markdown parsing as the primary contract.

## 6. Routing Consequences

Routing should depend primarily on structured metadata, not only on prose description similarity.

That means BuddySwitch should gradually support richer routing metadata such as:

- declared input slots
- declared output slot
- task kind compatibility
- explicit routing hints

This reduces ambiguity once a buddy owns multiple nearby skills.

## 7. Testing Consequences

Repo consistency tests should evolve from “does the markdown contain the right headings” toward package validation.

Minimum package validation should check:

1. `skill.toml` exists
2. `SKILL.md` exists
3. declared `output_schema` exists
4. referenced asset/example/reference/script paths exist
5. package buddy/id mapping matches manifest registration

This is much closer to the real scalability problem.

## 8. Relationship To Runtime

The package refactor follows the runtime refactor.

That ordering matters.

Skill packages should adapt to the new control plane rather than preserving current mixed responsibilities.

In practice:

- runtime owns deterministic control
- skill metadata declares contract surfaces
- `SKILL.md` guides execution
- package resources support execution and validation

## 9. Forward-Only Rules

- Do not keep markdown front matter as the long-term primary contract.
- Do not leave templates implied but unmaterialized.
- Do not treat supporting files as optional afterthoughts once the package contract is adopted.
- Do not package workflow control authority into skill prose when runtime can own it deterministically.
