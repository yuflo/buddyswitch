# BuddySwitch v1 — Switch Protocol

## 1. Purpose

The switch protocol is the primary interaction mechanism for BuddySwitch.

It lets the user explicitly choose which specialist agent should handle the current task.

## 2. Canonical syntax

```text
switch <agent>: <task>
```

Examples:

```text
switch market: Research 2026 demand for AI companion live spaces and write a report to artifacts/research/live-space.md
switch pm: Draft an MVP PRD from artifacts/research/live-space.md
switch design: Produce IA and core flows from artifacts/prd/live-space-mvp.md
switch dev: Implement the onboarding flow in projects/app based on artifacts/prd/live-space-mvp.md
switch test: Run smoke tests for the latest onboarding changes and write a report to artifacts/test/onboarding-smoke.md
```

## 3. Supported agents in v1

- market
- pm
- design
- dev
- test

## 4. Parsing rules

When the coding agent reads a user message:

1. detect whether it begins with the BuddySwitch switch directive
2. parse the target agent exactly
3. parse the remainder as the task body
4. apply only that agent's behavior and contract

## 5. Error handling

If the switch directive is invalid:

- explain the valid agent names
- do not silently guess the intended agent
- ask the user to reissue the directive clearly

If the syntax is malformed:

- explain the expected syntax
- provide one valid example

## 6. Routing rules

### Must
- obey the requested target agent
- keep the requested task body intact unless the user asks for reformulation
- use the requested agent's contract and templates

### Must not
- silently re-route the task to another agent
- invoke parallel agents without user request
- broaden the task beyond what the user asked

## 7. Output structure

Every switched run should return four blocks in the chat:

### A. Execution summary
A short plain-language summary of what the agent did.

### B. Working notes
A structured brief view of:
- assumptions
- decisions
- risks
- unknowns
or equivalent role-relevant notes

### C. Deliverables / changed files
- paths of generated files
- changed code files
- verification results if relevant

### D. Suggested next switch (optional)
A non-binding suggestion for which agent the user may want next.

## 8. Why BuddySwitch uses an explicit switch

BuddySwitch intentionally avoids hidden orchestration because the user wants:

- direct control
- predictable role selection
- simple collaboration
- easy mental model

The switch directive is a product decision, not only a prompt trick.

## 9. Future extension points

Possible future additions, not part of v1:

- `switch <agent> --brief: <task>`
- `switch <agent> --output <path>: <task>`
- `switch many: ...` for controlled parallel runs
- wrapper command such as `buddy <agent> "<task>"`

These are intentionally out of scope for the first version.
