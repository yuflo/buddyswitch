# BuddySwitch — Product Overview

## 1. What BuddySwitch is

BuddySwitch is a **project-embedded agent framework** for collaborative software and product development.

The user works inside a single workspace repository. Inside that repository, BuddySwitch provides:

- a shared entry contract
- a switch directive for selecting a specialist agent
- project files that teach the coding agent how the framework works
- role boundaries for each specialist agent
- structured output expectations
- conventions for durable artifacts vs temporary dumps

BuddySwitch is not a general autonomous team manager.
It does not add a mandatory team lead or hidden orchestration layer.
The user explicitly decides which agent should handle the current task.

## 2. Product goal

Enable a user to work with a coding agent like Codex CLI in a way that feels like:

- "switch to the right specialist quickly"
- "get a high-quality structured output"
- "keep context and artifacts organized inside the project"
- "iterate on the framework itself through real development usage"

## 3. Product thesis

Modern coding agents are already strong enough to act like specialized roles when given:

- clear project-level instructions
- stable role boundaries
- reusable skills
- structured deliverable contracts
- disciplined file layout

BuddySwitch packages those ingredients into a repeatable repository framework.

## 4. Who this is for

Primary user profile for v1:

- solo founder / builder
- small AI-native product team
- someone already comfortable using local coding agents
- someone who wants explicit manual control over role switching

## 5. Primary user experience

The user enters the workspace root and opens Codex CLI.

Example session shape:

1. user asks Codex to read the framework and explain how to use it
2. user issues a switch directive such as:
   - `switch pm: Draft an MVP PRD from artifacts/research/x.md`
   - `switch dev: Implement the onboarding flow in projects/app`
3. Codex routes to the requested specialist behavior
4. Codex produces:
   - a concise execution summary
   - structured working notes
   - changed files or deliverables
   - an optional next suggested switch
5. the user manually issues the next switch when ready

## 6. Product principles

### Explicit over implicit
The user chooses the agent directly. BuddySwitch does not silently re-route the task to another role.

### One repo, one working truth
The framework, project code, durable artifacts, and summaries live in one workspace repo.

### Durable artifacts over verbose chatter
Important outputs go into persistent files. Noisy raw dumps are separated.

### Specialist boundaries matter
Each agent should stay inside its role instead of becoming a generic all-purpose assistant.

### MVP first
The first version is optimized for Codex CLI validation, not broad multi-runtime parity.

## 7. What BuddySwitch is not

BuddySwitch v1 is not:

- a background autonomous PM
- a workflow engine
- a hidden multi-agent planner
- a deep enterprise governance platform
- a separate SaaS product UI
- a replacement for Git, CI, or normal software engineering discipline

## 8. Success criteria for v1

BuddySwitch v1 succeeds if:

1. Codex can enter the repo and correctly explain how BuddySwitch works
2. the user can switch to each of the five agents with a single directive
3. each agent produces outputs that match its contract
4. artifacts are organized cleanly enough for repeated iteration
5. the framework itself becomes easy to refine after 10–20 real usage cycles
