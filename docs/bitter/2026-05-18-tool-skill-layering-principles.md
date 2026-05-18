# Tool, Skill, And Prompt Layering Principles

Date: 2026-05-18
Status: distilled principle note from recent `docs/memo` discussions.

## Core Rule

BuddySwitch should let the host decide from runtime-visible tool semantics and tool feedback.

Do not compensate for unclear tool contracts by adding large prompt instructions, phrase triggers,
or long AGENTS manuals.

If the host must read service code, remember a hidden workflow, or infer state impact from
`ok=true`, the runtime contract is incomplete.

## Layer Responsibilities

### Tool Catalog

The tool catalog describes atomic capability meaning.

It should answer:

- what capability the tool provides;
- when the capability is appropriate;
- when it is not appropriate;
- what each action reads, writes, validates, creates, updates, deletes, issues, or opens;
- what each input means;
- what the action returns;
- what authority, ownership, visibility, and permission boundary applies;
- what side effects and durability the action has;
- what common failures mean.

It should not encode business workflow steps.

Examples that belong in the tool layer:

- `artifact.get` reads one readable artifact record with full body content by explicit artifact id.
- `artifact.list` returns artifact summaries, not full bodies.
- `buddybox.write` writes one active-buddy private file and does not mutate product objects.
- `track.add_material` publishes an artifact as the current shared material on a track.

Examples that do not belong in the tool layer:

- after writing a PRD, hand off to Design;
- if the user asks for a landing page, always use a PM skill;
- Market should search, issue evidence, then create an artifact;
- Dev should read source artifacts, implement, then hand off to Test.

### Tool Response

The tool response closes the loop after a call.

It must explain actual effect, not only success shape.

A strong response makes clear:

- whether state changed;
- which object ids changed;
- whether the result is durable or transient;
- whether the result is private or cross-buddy readable;
- what content level was returned: summary, body, metadata, token, file content, or browser intent;
- why a rejected call was blocked;
- whether a rejected call changed any state;
- which fields are correctable;
- which alternative atomic capabilities may be relevant.

`ok=true` without state impact is too weak for collaboration-critical tools.

### Skill

Skills own repeated business workflows.

They may describe how to combine atomic tools for recurring work such as PM source intake, PRD
writing, design shaping, implementation, testing, market research, or artifact publication.

Skills should:

- teach judgment and workflow sequencing;
- stay short enough to be operational;
- point back to runtime tool catalog and response feedback for action details;
- defer to `permission_boundary`, `why_blocked`, `state_changed`, `durability`, and other
  structured response fields.

Skills should not:

- duplicate the full tool schema;
- become brittle hardcoded scripts;
- override runtime feedback;
- hide missing tool capability behind memorized instructions.

### AGENTS

AGENTS stays short.

It should provide:

- project and role orientation;
- where to start, such as `context summarize`;
- where to inspect the full tool catalog;
- non-bypassable runtime boundaries;
- verification and safety rules.

It should not become:

- a tool encyclopedia;
- a payload schema catalog;
- a long buddy-specific SOP;
- a phrase-to-tool router;
- a prose mirror of runtime behavior.

### Context Discovery

Context discovery is progressive.

`context.summarize` should give compact first-pass tool affordances.

`context.get` and `turn_runtime.py status` should expose the full tool catalog and operation
semantics when the host needs detail.

Do not load every tool detail into default prompt text.

## Correction Principle

When behavior is wrong, fix the layer that owns the wrong contract.

- If a tool succeeds but does not mutate the state its contract implies, fix the service/store
  state transition.
- If a tool is hard to choose, improve `semantics.py` and compact affordances.
- If a response leaves the host guessing, improve response fields and rejection feedback.
- If a workflow repeats, encode it in a skill.
- If AGENTS is growing to explain every case, move detail down into tools, responses, or skills.

Do not solve tool-layer weakness with prompt bulk.

## Test Principle

Tests must prove semantic behavior and persisted state.

They should inspect:

- env.tool responses;
- persisted JSON;
- track visibility through `track.open`;
- artifact readability through `artifact.get`;
- rejection feedback and state unchanged guarantees.

They should not only assert:

- `ok=true`;
- field presence;
- registered action names;
- shallow command hints.

For collaboration-critical behavior, the test should catch a host-visible contract break.

## Current Track/Artifact Implication

The track/artifact path should have one coherent publication contract:

```text
artifact.create_revision = create an active-buddy-owned draft/revision content page
track.add_material       = publish that artifact as current shared track material
track.add_proof          = publish that artifact as close proof
track.open               = read current shared material/proof references
artifact.get             = read the full body of a readable artifact id
```

Under this model, `published_to_track` is not an independent direct-publish bypass. It is state
owned by track publication.

If `artifact.create_revision` claims publication through `published_to_track` but `track.open` does
not show the artifact, the fix is not more PM prompt text. The fix is to correct the tool contract,
state transition, response feedback, and tests.

## Short Diagnosis Rule

If a buddy acts generic after a runtime merge, first check whether tool semantics, responses, skills,
and state transitions still agree.

Only add prompt text after confirming the lower runtime contract is already correct and the remaining
problem is genuinely role guidance.
