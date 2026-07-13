---
name: synthesize-cross-functional-inputs
description: Use when PM must combine market, design, dev, test, or stakeholder signals into product implications.
---

# Synthesize Cross-Functional Inputs

## Purpose
- Map cross-functional signals to product impact instead of forwarding raw notes.
- Decide which inputs change scope, requirements, acceptance criteria, risk, or owner questions.

## Use when
- Market, design, dev, test, stakeholder, or proof inputs conflict or need prioritization.
- PM must decide what a signal means for the product path.

## Do not use when
- The task is to collect fresh market evidence, shape UI details, implement code, or execute tests.
- Inputs are already resolved into a clear PM decision and only need durable capture.

## Inputs
- Market evidence, design artifacts, dev reports, test proof, stakeholder constraints, current track state, and relevant artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Classify each signal by source, owner, evidence strength, and whether it is fact, assumption, or opinion.
2. Translate each signal into product impact: decision, scope, requirement, criteria, owner question, or risk.
3. Resolve contradictions when evidence is strong enough; otherwise name the blocker and next owner.
4. Publish durable synthesis with `artifact.create_revision` and `track.add_material` when it becomes shared product truth.

## Outputs
- Synthesis table or brief summary with signal, product impact, PM action, owner, and open question.
- Optional owner-specific task update.

## Quality Bar
- Market, design, dev, and test inputs are not flattened into generic consensus.
- PM makes the priority and tradeoff visible.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Read track context with `track.open` and full artifact bodies with `artifact.get` when ids matter.

## Examples
- Input: market pain is credible but narrow, design complexity is high, dev has reusable parts, and test missed mobile. Output: narrow scope, mobile criteria, design risk, and one open product question.

## Counterexamples
- Forwarding every input downstream without deciding what changes.
- Treating weak stakeholder preference as stronger than proof evidence.
