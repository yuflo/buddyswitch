# BuddySwitch v1 — Open Questions and Notes

## 1. Resolved decisions for v1

These decisions are treated as settled for the MVP:

- BuddySwitch is a project-level framework
- Codex CLI is the first target runtime
- the user explicitly chooses the agent
- no team lead role is included
- no mandatory workflow engine is included
- one workspace repo is used for the MVP
- durable artifacts and raw dumps are separated
- hooks are postponed until after basic validation

## 2. Still-open questions

### Q1. Should BuddySwitch later support a wrapper command?
Possible future shape:
- `buddy pm "draft prd from artifacts/research/x.md"`

This is not required for v1.

### Q2. Should there be an optional "strict mode"?
Strict mode could enforce:
- required output blocks
- required artifact file writing
- stronger rejection of ambiguous tasks

### Q3. How many skills per agent should exist after the MVP?
The MVP starts with one skill per agent.
Real usage should determine which extra skills are worth adding.

### Q4. How much Codex-specific language should live in canonical docs?
The canonical product docs should remain as neutral as possible,
while implementation notes can stay Codex-first.

### Q5. When should hooks be introduced?
Only after:
- switching works reliably
- contracts are stable
- artifact placement is stable
- real pain points justify deterministic scripts

## 3. Risks to watch while developing the MVP

- instructions becoming too long
- skills overlapping too much
- agents ignoring file placement rules
- raw dumps leaking into artifacts
- artifacts becoming too verbose and losing utility
- the framework becoming harder to understand than the work it is meant to support

## 4. Recommended discipline during the first 10–20 runs

After each real run, inspect:

1. did the requested agent stay inside its boundary?
2. was the output shape useful?
3. did the file placement make sense?
4. was anything too verbose?
5. what single instruction change would most improve the next run?

## 5. Reference implementation note

The first working BuddySwitch repo should prioritize:
- clarity
- inspectability
- iteration speed

not:
- completeness
- automation sophistication
- multi-runtime abstraction perfection
