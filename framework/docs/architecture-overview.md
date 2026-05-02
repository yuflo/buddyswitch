# BuddySwitch Architecture Overview

This document explains BuddySwitch in plain language.

If you remember only one thing, remember this:

- BuddySwitch controls the workflow.
- The host Codex session does the actual work.

## What BuddySwitch Is

BuddySwitch is not a standalone agent.

It is a control layer that runs inside a host coding-agent session.
In this repository, the normal host is the current Codex CLI session.

BuddySwitch is responsible for:

- preparing native turn context from the active instance metadata and `request_text`
- loading buddy and skill metadata
- returning the allowed skill candidates
- validating structured output
- persisting task, artifact, track, and run state
- keeping historical `switch ...` parsing isolated to debug/manual tooling

The host Codex session is responsible for:

- understanding the user's current request
- choosing one `skill_id` from the allowed candidates
- reading the selected `SKILL.md`
- executing the workflow
- producing structured output that matches the chosen schema

## The Two Main Parts

### 1. Host Codex Session

Think of the host as the worker and decision-maker.

It chooses a skill and performs the real task.

Examples:

- browse sources
- summarize evidence
- write a PRD
- implement code
- run tests

### 2. BuddySwitch Control Layer

Think of BuddySwitch as the traffic controller and recorder.

It decides:

- which active buddy the instance is bound to
- which skills are allowed for that buddy
- whether the request can be persisted safely
- where the resulting state should be written

It does not decide business quality and it does not run a second hidden LLM router.

## Canonical Flow

BuddySwitch uses one standard flow:

1. `prepare-turn-context`
2. `run`
3. `persist`

### Debug `parse`

Historical `switch ...` parsing is debug/manual tooling only. It reads an internal/debug wire command and breaks it into:

- `buddy`
- optional `task_id`
- optional `track_id`
- `demand`

Internal wire example:

```text
switch <buddy>: research demand for AI voice-enhanced headphones
```

becomes:

- `buddy = market`
- `demand = research demand for AI voice-enhanced headphones`

Product-mode buddy instances do not use this parser. The launcher has already selected one active buddy, and user text is handled as ordinary `request_text`.

### `prepare-turn-context`

Prepare execution context for the host session without writing final artifact output or run audit state.

Product mode selects the buddy at launcher startup and product-mode users send ordinary requests.
`prepare-turn-context` binds the active buddy from instance metadata and preserves the user's text as `request_text`; it does not parse the text as a routing command.

For create-mode requests, `turn_context` may materialize a zero-run task immediately in create mode.
`resolve_context` assigns the concrete `task_id`.
`resolve_context` reserves the next run envelope.

This step loads:

- the buddy definition from `buddyswitch/manifest.toml`
- the allowed skills for that buddy
- task context
- optional track context
- output schema paths

It returns fields such as:

- `instance_id`
- `active_buddy`
- `request_text`
- `current_task_id`
- `current_track_id`
- `skills`
- `task_context`
- `track_context`
- `inputs_by_skill`
- `run_envelope`
- `warnings`

Important rule:

- `prepare-turn-context` does not write final artifact output or run audit content. In create mode it may materialize a zero-run task and reserve the next run envelope so the host has a concrete task/run identity before execution.

### `run`

This step is performed by the host Codex session.

The host:

1. chooses one `skill_id`
2. reads `buddyswitch/skills/<buddy>/<skill>/SKILL.md`
3. executes the workflow
4. produces structured output matching the selected schema

### `persist`

This step writes canonical BuddySwitch state.

For create-mode switches, `persist` creates the task object, assigns the final task id, and then writes the resulting state and run audit data against that persisted task.

BuddySwitch validates:

- the selected `skill_id`
- schema shape
- safe state references

Then it writes:

- task objects under `buddyswitch/objects/tasks/`
- artifact objects under `buddyswitch/objects/artifacts/` when the selected skill produces artifacts
- run audit JSON under `buddyswitch/content/runs/`
- track objects when track mutations are part of the request

## How Skill Selection Works

Skill selection does not happen automatically inside BuddySwitch `prepare-turn-context`.

Instead:

1. BuddySwitch returns the allowed skill candidates in `turn_context.skills`.
2. The host Codex session chooses one of them.

This means:

- single-skill buddies may return `implicit_skill_id`
- multi-skill buddies do not auto-select

For multi-skill buddies, the host must choose explicitly before persistence.

## Example: A Market Request

Product-mode input in a `market` instance:

```text
Help me analyze the market for AI voice-enhanced headphones
```

Current `market` buddy behavior:

1. `prepare-turn-context` reads `active_buddy = market` from instance metadata and preserves the text as `request_text`
2. It loads the `market` buddy and returns:
   - `skills = ["research-scan", "pmf-recon", "customer-discovery", "positioning-copy", "channel-discovery", "launch-prep"]`
   - `task_context`
   - optional `track_context`
   - `run_envelope`
   - host-facing execution metadata in each resolved skill card
3. The host chooses the skill:
   - choose `research-scan` for broad market/category/competitor/demand analysis
   - choose `pmf-recon` for PMF-oriented validation such as ICP, pain intensity, alternatives, and next validation action
   - choose `customer-discovery` for interview planning and problem discovery
   - choose `positioning-copy` for founder-facing positioning and message framing
   - choose `channel-discovery` for first-channel selection and channel experiment planning
   - choose `launch-prep` for launch-ready validation prep and feedback-loop setup
4. The host executes the chosen skill
5. `persist` writes the result only after the host provides:
   - the resolved payload
   - the chosen `skill_id`
   - a schema-valid structured result

## What Lives Where

### Canonical formal docs

Formal BuddySwitch specs live under:

- `framework/docs/`

These are the main entry points:

- `framework/docs/architecture-overview.md`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`

### Working materials

Development notes, plans, reviews, and whiteboards live under:

- `docs/`

These are useful during implementation, but they are not the main public architecture entry point.

## Mental Model

Use this shortcut:

- Product mode selects the buddy when the launcher starts.
- Product-mode users send ordinary requests.
- The canonical wire form remains internal/debug `switch ...`.
- Product-mode text is preserved as `request_text` and never rewritten into a command.

- instance metadata tells BuddySwitch which buddy owns the request
- BuddySwitch tells the host which skills are allowed
- the host chooses one skill and does the work
- BuddySwitch validates and records the result

That is the core architecture.
