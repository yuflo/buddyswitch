# Memo To Goals

Use this reference when the user supplies a feature memo, implementation memo, PRD-style note, or broad target.

## Objective

Convert the memo into a small set of user-verifiable effects before choosing tests. Do this internally and present only one concise correction checkpoint unless a risk confirmation is required.

## Read Order

1. Read the memo title, `Goal`, `Task Goal Restatement`, and any primary user loop.
2. Read `Non-Negotiable Requirements`, target model, acceptance criteria, and verification sections.
3. Read `Out Of Scope` and deletion/residue requirements.
4. Skim file maps only to identify surfaces and actors. Do not turn file lists into goals.

## Extraction Rules

Extract 2-5 effects. Fewer is better when they cover the real product promise.

Classify every candidate:

| Type | Meaning | Example |
| --- | --- | --- |
| `P0 user effect` | A user can directly perceive or perform it. | Web opens Team room and Tracks instead of Actor Console. |
| `P1 stability invariant` | Needed so the user effect stays correct under realistic use. | Repeated side sends keep the same actor, side thread, and turn target. |
| `P2 residue guard` | Proves old behavior, names, or paths did not remain visible. | No live WebUI surface still shows Actor Console or Create Actor. |
| `Out of scope` | Explicitly excluded from the memo's success definition. | Do not test actor-created tasks as success when memo says system ingress owns creation. |

Prefer outcomes shaped like:

```text
When <user/actor> does <behavior>, BuddySwitch should <observable effect>,
without <forbidden residue or wrong target>.
```

## Systemic Challenges To Apply

Challenge the plan when:

- The "goal" is a module name, file name, or helper function rather than a product effect.
- The test would only prove implementation shape, not user behavior.
- The desired stability claim requires live, multi-entry, stress, or recovery gates that the user did not permit.
- A broad memo contains several independent product effects; split and prioritize instead of making one giant simulation.
- The memo explicitly excludes a behavior but the test plan treats it as success.
- The evidence path is not stated and the work would become hard to resume.

## Correction Checkpoint Template

Use this after memo analysis and strategy selection:

```markdown
## Simulation Checkpoint
I will verify:
1. [P0] <effect and why it matters>
2. [P1] <stability invariant and failure it prevents>
3. [P2] <residue guard if relevant>

I will use:
- Means: <browser UI | Web API | CLI | IM wake | Track wake | browser/cockpit | fake/live | stress>
- Gates: <G0..G4>
- Records: <path>

I will not claim:
- <skipped or weak coverage>

Proceeding unless you want to change this.
```

Keep this short. The user should be able to correct it quickly. Do not ask them to approve every inferred field.

## From Memo Examples

### Side-thread lifecycle memo

Likely effects:

- `[P0/P1]` Application-class wake/input flows create and use side threads through one lifecycle owner without wrong target steering.
- `[P1]` Side send/close uses stored side-thread and turn identity, including repeated and stale-id probes.
- `[P2]` Old direct app-server plus registry composition and `thread/turns/list` cleanup residue is absent from live paths.

### WebUI Team Room memo

Likely effects:

- `[P0]` Web Management first screen reads as Team room and Tracks, not Actor Console.
- `[P0]` Selecting a teammate opens the direct conversation using existing IM APIs.
- `[P2]` Old Actor Console, Create Actor, fake collaboration, and Track write UI are absent from live surface.

### Task Sys rebuild memo

Likely effects:

- `[P0/P1]` One inbound item becomes one actor-owned task with clear lifecycle visibility.
- `[P1]` Frames and turn-completed events update or drive existing task lifecycle instead of creating separate tasks.
- `[P2]` Checkpoint task terminology and actor-facing checkpoint tools are gone from user-visible/runtime guidance surfaces.
