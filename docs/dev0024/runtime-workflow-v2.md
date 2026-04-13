# BuddySwitch Runtime And Workflow V2

## Status

- Date: 2026-04-14
- Status: Draft
- Scope: `parse -> resolve -> run -> persist` control behavior for BuddySwitch v2

## 1. Goal

BuddySwitch v2 keeps the existing four-stage runtime model:

1. `parse`
2. `resolve`
3. `run`
4. `persist`

The structural change is not the stage count.
The structural change is authority cleanup.

Runtime and workflow become the only owners of deterministic control behavior.
Skills produce domain work, not parallel control decisions.

## 2. Problems In The Current Model

The current runtime already generates:

- `reference_switches`
- `recommended_switch`
- deterministic artifact selection inputs

But the skill output contract still allows overlapping control behavior such as:

- `suggested_next_switch`
- loosely defined readiness behavior inside skill prose
- variable artifact-reading behavior depending on host interpretation

That creates dual authority.

BuddySwitch v2 removes that ambiguity.

## 3. Core Decision

Runtime owns deterministic control behavior.
Workflow owns fixed execution sequencing.
Skill owns content generation and domain-specific judgment inside its defined boundary.

## 4. Stage Responsibilities

## 4.1 Parse

`parse` remains responsible for:

- recognizing canonical switch syntax
- tolerating minor spacing normalization
- rejecting invalid buddy or empty demand

No change in role.

## 4.2 Resolve

`resolve` becomes the assembly point for all deterministic pre-run context.

It must:

1. parse invocation
2. resolve buddy, task, and track binding
3. load skill catalog metadata for the resolved buddy
4. assemble task context
5. assemble track context when applicable
6. compute artifact selection using v2 slot-based semantics
7. emit authoritative command templates
8. return enough structured context for host execution

It must not:

- write BuddySwitch state
- ask the skill to define next-step command authority
- leave artifact selection authority implicit

## 4.3 Run

`run` still belongs to the host session.

Host responsibilities:

1. choose exactly one eligible skill
2. read the selected skill package instructions
3. read the selected input artifacts
4. execute the skill
5. produce a structured result matching the output schema

Run may include model judgment.
Run must not override runtime authority.

## 4.4 Persist

`persist` remains a technical gate.

It validates:

- selected skill is allowed
- output schema matches
- task/track references are safe
- artifact slot/revision write rules are respected

It writes:

- task
- artifact
- run
- track when needed

It does not evaluate business quality.

## 5. Deterministic Authorities

BuddySwitch v2 makes the following authorities exclusive.

## 5.1 Command Authority

Runtime is the only source of next-step commands.

Allowed output surfaces:

- `reference_switches`
- `recommended_switch`

Retired:

- `suggested_next_switch`

Skills may still produce advisory notes such as:

- open questions
- risks
- suggested follow-up themes

They may not produce command-shaped control authority.

## 5.2 Artifact Selection Authority

Artifact selection is determined by runtime/workflow using slot semantics.

Default rule:

- select current artifact per required upstream slot

Optional extension rule:

- include previous revision when workflow explicitly asks for comparison or history

The host session should not improvise artifact authority outside this deterministic selection path.

## 5.3 Stage Gate Authority

Readiness checks and handoff gates belong to workflow or runtime, not to output-producing skills.

Examples:

- “does dev have required upstream inputs”
- “are open questions below handoff threshold”
- “is there a current PRD/design spec in required slots”

These are fixed control questions and should be evaluated outside the skill body.

## 6. Workflow Shape

Recommended fixed workflow:

1. `resolve`
2. choose skill
3. read selected input artifacts by slot
4. execute skill
5. `persist`
6. render receipt/commands/summary

This is intentionally simple.

## 7. Input Selection Model

In v2, skill metadata should declare expected input slots, for example:

- dev implement task requires `prd` and optionally `design-spec`
- test smoke test requires `implementation-report`
- design IA spec requires `prd`

Skills that do not persist artifacts, such as track lifecycle workflows, may declare no `input_slots` and no `output_slot`.

Runtime uses those declarations to compute selected artifacts.

Result shape should evolve from generic id lists toward slot-aware selection.

Recommended shape:

```json
{
  "selected_inputs": [
    {
      "slot": "prd",
      "artifact_id": "art-task-pm-onboarding-prd-r3",
      "revision": 3,
      "selection_reason": "current artifact for required upstream slot"
    }
  ]
}
```

## 8. Handoff Model

Handoff is not a separate persisted object.

Handoff is the outcome of:

- track progression
- current-buddy and next-buddy semantics
- current artifacts by required slots
- runtime-generated switch references

This keeps handoff deterministic and inspectable.

## 9. Receipt Contract

The terminal surface can keep the existing three sections:

- `Receipt`
- `Commands`
- `Summary`

But the meaning tightens:

- `Commands` is runtime authority only
- `Summary` is execution outcome only
- `Receipt` reflects current persisted state after v2 slot/revision writes

## 10. Forward-Only Rules

- Do not preserve `suggested_next_switch`.
- Do not allow skills to emit parallel command authority.
- Do not keep old artifact selection and new slot-based selection in parallel.
- Do not embed workflow gates as hidden prompt conventions inside skills.
