---
name: write-requirements
description: Use when PM must turn product goals and scope into observable requirements for design, dev, or test.
---

# Write Requirements

## Purpose
- Express product behavior without owning UI craft or implementation details.
- Give design, dev, and test a shared behavior target.

## Use when
- Goals and scope exist but need observable requirements.
- A request uses vague terms that must become actor, trigger, behavior, constraint, and rationale.

## Do not use when
- PM has not yet framed direction or defined scope.
- The task is acceptance criteria only, implementation instructions, or visual specification.

## Inputs
- Product direction, scope, decisions, design constraints, technical constraints, user flows, current track state, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`, and runtime response fields.

## Steps
1. Convert goals into observable user or system behavior.
2. Split requirement from acceptance criteria; keep verification details in criteria.
3. Mark owner boundary for PM, design, dev, and test decisions.
4. Record assumptions and publish durable requirements through `artifact.create_revision` and `track.add_material` when shared.

## Outputs
- Numbered requirements with actor, trigger, behavior, constraint, rationale, assumptions, and owner boundary.

## Quality Bar
- Test can understand what behavior exists without PM interpretation.
- Requirements avoid prescribing component internals or visual craft.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use `track.open` and `artifact.get` before revising existing product material.

## Examples
- Input: "Make onboarding easier and more premium." Output: observable behavior by actor and trigger, constraints, rationale, and boundaries left to design/dev.

## Counterexamples
- "Make it better" as a requirement.
- "Use React component X" as a PM requirement.
