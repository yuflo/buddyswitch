# AI Task Preflight

Use this before analysis, planning, or implementation on any medium or large task.

## Required Checks

### 1. Outcome and bottleneck
- What concrete outcome is being advanced?
- Why is this the current bottleneck?

### 2. Confirmed facts
- Which facts are confirmed from repo files, code, logs, commands, or tests?
- What evidence backs each fact?

### 3. Open unknowns
- Which assumptions are still open?
- Which unknowns would change the chosen approach if they prove false?

### 4. Boundaries and non-goals
- Which contracts, schemas, prompts, APIs, or product semantics constrain this task?
- What is explicitly out of scope?

### 5. Tools and permissions
- Which tools are required for the next step?
- Are they available now?
- Does the next step cross `tool_scope`, need takeover, or require user approval?

### 6. Verification plan
- What command, test, inspection, or main-path run will prove success?
- What result will count as failure and force a rethink?

## Stop Conditions

Stop and resolve before execution when:

- a required tool or permission is missing
- a contract boundary is unclear
- the only current plan depends on an unverified assumption
- the claimed fix has no concrete verification path
