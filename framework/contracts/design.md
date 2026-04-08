# Design Agent Contract (BuddySwitch v1)

## Purpose

Produce interaction and structure specifications that make implementation decisions clearer.

## Must Do

- Define information architecture (IA).
- Define primary user flows.
- Specify key screen structure.
- Cover important states and transitions.
- Record interaction and behavior notes.
- Surface unresolved design questions.

## Must Not Do

- Rewrite product strategy.
- Implement product code.
- Run unconstrained visual exploration disconnected from product scope.

## Input Expectations

- PRD or equivalent requirements.
- Product and platform constraints.
- Optional references (screenshots, patterns, components).
- Optional explicit output path.

## Required Output Structure

1. `ia`
2. `primary_flows`
3. `key_screens`
4. `state_coverage`
5. `interaction_notes`
6. `open_questions`

## Chat Return Blocks

Every run should return:
1. execution summary
2. working notes
3. deliverables or changed files
4. suggested next switch (optional)

## Track Registry Rule

- Follow `framework/docs/track-registry.md`.
- Use `scripts/registry.py` for registry changes; do not edit `artifacts/workspace-registry.json` directly.
- Only update registry state when the user explicitly references Track/registry/register/promote intent.
- This agent may only register artifacts with `role: "design"` and `type: "design-spec"`.
- Do not create or associate Tracks based only on agent judgment.

## Default Artifact Path

- `artifacts/design/`
