# BuddySwitch v1 — MVP PRD

## 1. Problem

When using coding agents for real product work, users often face three recurring issues:

1. the agent behaves too generically instead of acting like a specialist
2. process output is messy and hard to hand off between roles
3. project-level instructions, artifacts, and temporary dumps become disorganized

For BuddySwitch, the goal is to solve these problems inside a normal project workspace.

## 2. Product objective

Create a first-version framework that lets a user:

- open a workspace with Codex CLI
- let Codex understand the framework from repo files
- switch explicitly to a desired specialist agent
- receive structured, role-specific outputs
- keep durable outputs and noisy intermediate dumps organized

## 3. User story

As a builder using Codex CLI inside a local workspace,
I want to switch directly to a specialist agent such as PM, design, dev, or test,
so that I can get clearer role-specific outputs without manually re-explaining the whole working style every time.

## 4. Core jobs to be done

- route the current task to the correct specialist role
- preserve role boundaries
- standardize process output shape
- define where deliverables should be written
- keep the framework simple enough to evolve through usage

## 5. In scope for MVP

### P0
- root `AGENTS.md` as the framework entry point
- project-scoped Codex config
- project-scoped custom agents for:
  - market
  - pm
  - design
  - dev
  - test
- switch directive:
  - `switch <agent>: <task>`
- role boundaries for all five agents
- output contracts for all five agents
- one starter skill per agent
- shared workspace directory conventions
- artifact vs raw dump conventions
- minimal evaluation cases

### P1
- more than one skill per agent
- stronger templates for recurring work
- lightweight hooks for deterministic validation
- optional wrapper script for generating switch prompts
- multiple project apps under `projects/`

## 6. Out of scope for MVP

- automatic task decomposition
- team lead or planner role
- hidden re-routing across agents
- complex parallel orchestration
- a polished visual UI
- hosted SaaS deployment
- enterprise policy engine
- multi-runtime perfect compatibility on day one

## 7. Functional requirements

### FR-1: Framework discoverability
The coding agent must be able to understand the framework by reading repository files.

### FR-2: Switch parsing
The framework must define a stable switch syntax:
`switch <agent>: <task>`

### FR-3: Agent invocation
When a valid switch directive is used, the requested agent behavior must be applied.

### FR-4: Role boundaries
Each agent must have an explicit scope and non-scope.

### FR-5: Structured output
Each run must return:
- execution summary
- working notes
- deliverables or changed files
- optional next suggested switch

### FR-6: File placement
Durable outputs must go to `artifacts/`.
Noisy dumps must go to `runs/raw/`.
Compact run notes should go to `runs/summaries/`.

### FR-7: Project code separation
Actual application code must live under `projects/app/` for the MVP reference workspace.

## 8. Non-functional requirements

- low setup friction
- readable repository structure
- easy Git synchronization
- easy manual inspection
- strong enough conventions for repeated use
- minimal accidental framework drift

## 9. Agent roster

- market
- pm
- design
- dev
- test

## 10. Acceptance criteria

### AC-1
Codex can explain how to use BuddySwitch after reading the repo root instructions.

### AC-2
A valid `switch pm:` request produces a PRD-shaped output and writes it to `artifacts/prd/`.

### AC-3
A valid `switch design:` request produces design-structured output and writes it to `artifacts/design/`.

### AC-4
A valid `switch dev:` request limits implementation work to the intended project area and clearly reports changed files.

### AC-5
A valid `switch test:` request returns pass/fail/blocked structure and writes a durable test report.

### AC-6
Invalid switch directives are rejected clearly instead of being silently guessed.

### AC-7
The workspace remains understandable after repeated runs because artifacts and dumps are separated.

## 11. Risks

- agent role drift if instructions are too loose
- too many files too early causing framework bloat
- noisy dumps leaking into Git history
- overfitting to Codex-specific assumptions
- the switch syntax being recognized inconsistently if instructions are weak

## 12. Recommended first implementation milestone

The first milestone should get the following working end-to-end:

1. `AGENTS.md`
2. `.codex/config.toml`
3. 5 custom agents
4. 5 contracts
5. 5 minimal skills
6. workspace folders
7. 5 evaluation prompts
