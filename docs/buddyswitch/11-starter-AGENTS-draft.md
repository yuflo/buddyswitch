# Starter Draft — AGENTS.md

This file is a draft that can be adapted into the real repository root `AGENTS.md`.

```md
# BuddySwitch Framework

This repository uses **BuddySwitch**, a project-level specialist-agent framework for collaborative software and product development.

## How to use

Use the switch directive:

switch <agent>: <task>

Examples:
- switch market: Research demand for AI companion live spaces and write the result to artifacts/research/live-space.md
- switch pm: Draft an MVP PRD from artifacts/research/live-space.md
- switch design: Produce IA and core flows from artifacts/prd/live-space-mvp.md
- switch dev: Implement the onboarding flow in projects/app based on artifacts/prd/live-space-mvp.md
- switch test: Run smoke tests for the latest onboarding changes and write a report to artifacts/test/

## Available agents

- market
- pm
- design
- dev
- test

## Required behavior

When the user writes `switch <agent>: <task>`, you must:

1. route the task to that agent only
2. obey that agent's role boundary
3. read:
   - `framework/contracts/<agent>.md`
   - relevant files in `framework/templates/`
   - relevant referenced artifacts
   - relevant repo-local skills in `.agents/skills/`
4. return:
   - execution summary
   - working notes
   - deliverables or changed files
   - suggested next switch (optional)

## Switch rules

- treat `switch <agent>:` as a framework directive
- do not silently guess unknown agent names
- do not silently reroute to a different agent
- do not use multiple agents unless the user explicitly asks

## File placement

- durable outputs go to `artifacts/`
- noisy raw dumps go to `runs/raw/`
- compact useful summaries go to `runs/summaries/`

## Project code location

The main product code lives in `projects/app/`.
```
