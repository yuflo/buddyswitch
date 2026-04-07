# BuddySwitch v1 — Evaluation Plan

## 1. Why BuddySwitch needs evals

BuddySwitch is a framework.
Its quality depends on whether the agents actually follow the intended behaviors.

Without lightweight evaluation, the framework will drift and regress silently.

## 2. Evaluation philosophy

Keep the first evaluation suite extremely small.

The goal is not benchmark theater.
The goal is to detect whether the framework still behaves correctly after changes.

## 3. MVP evaluation scope

Create five small cases, one per critical behavior:

### Case 1 — framework discoverability
Prompt:
- `Read AGENTS.md and explain how this framework works.`

Check:
- does Codex explain BuddySwitch correctly?
- does it mention the switch syntax?
- does it mention the five agents?

### Case 2 — pm contract adherence
Prompt:
- `switch pm: Draft an MVP PRD from artifacts/research/sample.md`

Check:
- does the output include goals and non-goals?
- does it include P0/P1 scope?
- is the file written to `artifacts/prd/`?

### Case 3 — design contract adherence
Prompt:
- `switch design: Produce IA and core flows from artifacts/prd/sample.md`

Check:
- does the output include IA?
- does it include state coverage?
- is the file written to `artifacts/design/`?

### Case 4 — dev boundary adherence
Prompt:
- `switch dev: Implement the requested change in projects/app`

Check:
- are changed files reported?
- does the work stay inside intended project areas?
- is there some verification output?

### Case 5 — invalid switch handling
Prompt:
- `switch potato: do something`

Check:
- does Codex reject the agent name clearly?
- does it provide valid agent options?
- does it avoid silently guessing?

## 4. Output scoring

Use simple pass/fail or 0/1 scoring first.
Do not overcomplicate with weighted multi-dimensional rubrics.

## 5. Recommended eval structure

```text
evals/
├─ cases/
│  ├─ 01-framework-discoverability.md
│  ├─ 02-pm-contract.md
│  ├─ 03-design-contract.md
│  ├─ 04-dev-boundary.md
│  └─ 05-invalid-switch.md
└─ rubrics/
   └─ base-rubric.md
```

## 6. When to run evals

Run the minimal eval suite whenever:
- `AGENTS.md` changes
- agent TOML files change
- contracts change
- skills change
- switch syntax changes

## 7. Definition of a useful evaluation result

A useful result should tell the user one of three things:

- the framework still behaves correctly
- a specific behavior regressed
- a specific instruction is too weak or ambiguous

## 8. What not to do in v1

Do not build:
- a full hosted evaluation platform
- a giant benchmark suite
- a complicated analytics dashboard

Keep the eval system lightweight and close to real usage.
