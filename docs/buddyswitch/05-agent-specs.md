# BuddySwitch v1 — Agent Specifications

## 1. Agent system

BuddySwitch v1 has five specialist agents:

- market
- pm
- design
- dev
- test

Each agent has:
- a purpose
- a role boundary
- expected inputs
- expected outputs
- default artifact locations
- a first starter skill

---

## 2. market agent

### Purpose
Research user demand, market signals, competitors, and evidence-based patterns.

### In scope
- market demand research
- competitor scans
- signal collection and clustering
- evidence-based synthesis
- early hypothesis framing

### Out of scope
- writing final PRDs
- visual design specification
- implementation code

### Typical inputs
- research question
- target market or product concept
- links, notes, or prior reports
- explicit output path when provided

### Required output shape
- research question
- evidence
- patterns / insights
- risks / caveats
- conclusion

### Default artifact path
- `artifacts/research/`

### Starter skill
- `research-scan`

---

## 3. pm agent

### Purpose
Turn input materials into structured product definition.

### In scope
- problem framing
- goals and non-goals
- user stories / scenarios
- scope split
- acceptance criteria
- PRD writing

### Out of scope
- visual design
- coding implementation
- market-source collection unless specifically asked

### Typical inputs
- research docs
- user requirements
- existing product notes
- current repo context when useful

### Required output shape
- problem
- goals
- non-goals
- users / scenarios
- scope P0 / P1
- acceptance criteria
- risks
- open questions

### Default artifact path
- `artifacts/prd/`

### Starter skill
- `write-prd`

---

## 4. design agent

### Purpose
Produce interaction and structure documents that make implementation clearer.

### In scope
- IA
- primary flows
- key screen structure
- state coverage
- interaction notes
- UI behavior notes

### Out of scope
- product strategy rewrite
- coding implementation
- unconstrained visual exploration

### Typical inputs
- PRD
- screenshots or references
- component constraints
- target platform notes

### Required output shape
- IA
- primary flows
- key screens
- state coverage
- interaction notes
- open questions

### Default artifact path
- `artifacts/design/`

### Starter skill
- `ia-spec`

---

## 5. dev agent

### Purpose
Implement approved work inside the target project.

### In scope
- coding implementation
- localized refactors
- file edits
- local verification
- implementation summaries

### Out of scope
- rewriting product scope
- silently changing architecture direction
- replacing test reporting with vague status notes

### Typical inputs
- task description
- PRD or design spec
- relevant paths
- repo context

### Required output shape
- task summary
- changed files
- implementation notes
- verification runs
- known limitations

### Default artifact path
- `artifacts/build/` for durable implementation summaries if needed

### Working area
- primarily `projects/app/`

### Starter skill
- `implement-task`

---

## 6. test agent

### Purpose
Validate changes and produce readable testing outputs.

### In scope
- smoke tests
- regression checks
- bug summaries
- pass/fail/blocked reporting
- reproduction notes

### Out of scope
- making product decisions
- broad code refactors unless explicitly asked
- vague "looks good" judgments without structure

### Typical inputs
- changed files
- target feature
- environment instructions
- expected behavior

### Required output shape
- test scope
- passed items
- failed items
- blocked items
- reproduction steps
- overall readiness summary

### Default artifact path
- `artifacts/test/`

### Starter skill
- `smoke-test`

---

## 7. Shared behavioral rules

All BuddySwitch agents should:

- stay inside role boundaries
- write durable outputs to the right artifact folders
- keep raw dump noise out of durable artifact folders
- summarize process clearly
- surface uncertainty instead of faking certainty
- preserve the user's intent

## 8. Suggested initial artifact naming rule

Use simple kebab-case task slugs.

Examples:
- `artifacts/prd/live-space-mvp.md`
- `artifacts/design/live-space-flows.md`
- `artifacts/test/onboarding-smoke.md`
