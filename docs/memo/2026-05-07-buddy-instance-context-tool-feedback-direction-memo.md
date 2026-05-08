# Buddy Instance Context And Tool Feedback Direction Memo

## Context

After the buddy instance environment tool layer iteration, product-side testing
raised a PM buddy behavior question with this request:

```text
给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track
```

The PM buddy log showed a lot of source reading, schema inspection, runtime
contract inference, and local decision-making that looked like the LLM was
"摸索". The important conclusion is that this should not be treated as a narrow
AI scheduling landing page case. It is diagnostic evidence for the broader
direction of buddy instance productization.

Before this iteration, the intended first step for buddy instances was already:

```text
更多的上下文、工具的权限
```

The goal is to make buddy behavior converge because the runtime gives enough
executable context, enough enforced capability boundaries, and enough
tool-level feedback. The goal is not to add prompt patches for each observed
test case.

## Direction Definition

The optimization direction has three layers.

### 1. Executed Capability Boundary

This answers what the buddy can and cannot do, and it must be enforced by the
environment instead of relying only on model obedience.

Examples:

- per-buddy environment profiles
- Codex sandbox roots
- product `prepare` / `persist` runtime broker
- browser evidence gates for Market
- active-buddy-only native skills
- runtime `AGENTS.md` projection

This iteration materially advanced this layer. Buddy instances now have clearer
execution boundaries and more tool permission structure than before.

### 2. Context Projection

This answers what the buddy already knows when it starts a turn.

Examples:

- active buddy identity and role boundary
- current task and current track
- artifact index and relevant source/state paths
- active native skills
- scratch directory and read/write boundaries
- handoff context from prior buddy runs

This iteration partially advanced this layer through generated/runtime
instructions, active skill materialization, and profile-derived boundary
descriptions. It is not complete yet because the current prepared turn still
does not expose enough executable capability, payload, permission, and feedback
context for the host to avoid source/schema inference.

### 3. Tool Semantic Feedback

This answers how tools explain the next correct action to the buddy.

Examples:

- buddy-facing `prepare` / `persist` help
- explicit product-mode error messages
- compact canonical payload examples
- receipts and handoff metadata that tell the host how to finish safely
- stop conditions such as "broker unavailable: stop and report, do not bypass"

This is the weakest layer after the current iteration. The environment now has
more permission structure, but tool descriptions, errors, and recipes do not yet
guide the model strongly enough to avoid source/schema exploration.

## Current State After This Iteration

### Completed

- Buddy-specific runtime execution boundaries are stronger.
- Product-mode runtime now has profile-driven sandbox and broker structure.
- Market browser-native evidence can be treated as a capability boundary instead
  of only a prompt preference.
- Runtime skills are projected for the active buddy instead of exposing an
  unconstrained shared toolbox.
- Product `prepare` / `persist` paths exist as the main lifecycle interface for
  artifact and state changes.

### Partial

- Runtime `AGENTS.md` and projected docs now carry more context, but they are
  still not enough to replace canonical action recipes.
- PM can recognize that `projects/app` is not the correct write target, but the
  product flow does not yet make the PRD/track/handoff path obvious enough.
- Track and artifact state exist, but the current main loop still makes the
  host infer too much of the persist and handoff contract from surrounding
  documentation or source.

### Still Weak

- Tool help and error output are not yet written as product APIs for buddies.
- Runtime contracts and skill docs can disagree on expected payload shape.
- A buddy may inspect source code or schemas to infer behavior that should have
  been exposed by the tool itself.
- Missing context may look like an LLM reasoning problem even when the deeper
  issue is environment feedback.

## PM Buddy Log Diagnosis

The PM buddy log showed several correct behaviors:

- It stayed in the PM instance rather than switching roles.
- It recognized that both `write-prd` and `track-manager` skills were relevant.
- It treated `projects/app` as inappropriate for direct PM implementation.
- It understood that `prepare` / `persist` and `state_effects.track` were the
  correct lifecycle path.
- It avoided directly mutating raw BuddySwitch state.

The same log also exposed productization gaps:

- It read `turn_runtime.py`, schemas, manifests, and templates to infer the
  runtime contract.
- It interpreted a broker/socket permission issue as something that might need
  escalation or a workaround. Product-mode buddies should instead receive a
  clear stop condition.
- It decided to create a scratch HTML prototype for the landing page wording.
  For PM, the more correct main path is PRD plus track creation plus handoff to
  Design or Dev, unless the user explicitly asks PM for a throwaway prototype.
- It had to decide too much from first principles because the runtime did not
  provide a compact, canonical PM recipe for "product definition + track
  lifecycle".

This is not a failure of one prompt. It is evidence that the next bottleneck is
context/tool feedback productization.

## Why The Log Looked Like LLM Exploration

The exploration came from several systemic causes:

- The environment exposed constraints, but not enough canonical execution
  recipes.
- The request mixed product definition, track lifecycle, and "landing page"
  wording, which can imply implementation unless PM boundaries and handoff
  rules are explicit.
- PM skill documentation and runtime `persist` behavior were not perfectly
  aligned. Skill docs refer to richer PM result structures, while runtime
  `persist` accepts a compact buddy-run payload with artifacts, state effects,
  handoff, and contributor audit metadata.
- CLI help, broker errors, and receipts were not yet buddy-facing enough.
- Product mode could eventually grow continuation UX from an existing track,
  receipt, or handoff, but that is a product-flow design question and is not the
  current optimization target.

Because those feedback surfaces are incomplete, the model compensates by reading
source code and making local inferences. That looks like "摸索", but the root
cause is that the system did not yet make the correct path sufficiently obvious
and executable.

## Anti-Specialization Rule

Do not optimize for the literal AI scheduling landing page case.

The stable pattern is:

```text
PM product definition + lifecycle state change + handoff
```

Future fixes should be expressed at that intent level, not as rules like "when
the product is an AI calendar tool, do X".

Good examples should cover multiple variants:

- new feature PRD plus track creation
- scope update plus track advancement
- user feedback triage plus PM decision artifact
- PRD handoff from PM to Market or Design
- research handoff from Market back to PM

This avoids hard-coding one observed prompt while still making similar cases
converge.

## Confirmed Optimization Principle

The only accepted optimization path for the next iteration is:

```text
Increase and improve executable context inside the buddy instance env so the
same host, codex-cli, behaves better without larger or more specific prompts.
```

This means:

- `AGENTS.md` should remain a framework-level runtime specification, not a
  place for task-specific explanation.
- Context should come from the runtime environment: prepared task, track,
  artifacts, boundaries, active skills, permissions, receipts, handoff metadata,
  and tool feedback.
- Tool and skill surfaces should provide feedback signals: what is allowed,
  what was rejected, why it was rejected, and what safe next action exists.
- Do not solve buddy drift by adding larger prompt guidance or case-specific
  examples for one observed request.

## Next Main-Path Tasks

The next work should stay inside the existing buddy instance env main path:

```text
instance start/open -> workspace/env materialization -> prepare -> host skill
work -> persist -> receipt/handoff feedback
```

Do not touch peripheral systems for this iteration, including the context panel,
cleanup tools, debug object APIs, or skill importer. The goal is main-path
convergence, not broad repo cleanup.

### 1. Executable `prepare` Context

Add a compact runtime context block to `prepare` so the host can see the active
buddy's executable boundaries without reading source, schemas, profiles, or
manifest files.

Needed context:

- active buddy and active native skill ids
- allowed artifact kinds
- allowed `state_effects`
- handoff targets
- scratch and project read/write boundaries
- Market browser evidence requirement
- compact persist payload hints
- current task, track, artifact, and handoff summaries

Acceptance signal:

- PM, Market, and Dev `prepare` outputs make allowed actions, forbidden actions,
  and persist shape obvious from the returned JSON.
- A buddy should not need to inspect `manifest.toml`, env profiles, JSON schemas,
  or Python source to know the current turn's execution boundary.

### 2. Structured Tool And Skill Feedback

Improve existing runtime tools so success and failure outputs are buddy-facing
feedback signals rather than generic errors.

Needed feedback:

- broker unavailable: stop and report; do not bypass product-mode broker
- persist rejected: explain the violated boundary and allowed next action
- permission denied: name the permission boundary and current buddy capability
- Market evidence missing: show how to issue evidence and where to put it in
  `tool_evidence`
- browser evidence issued: return token mode, browser URL when relevant, persist
  field name, token scope, and next action

Acceptance signal:

- Key failures return structured fields such as `permission_boundary`,
  `stop_condition`, `allowed_next_actions`, or `command_hint`.
- A buddy can recover from missing evidence or invalid persist payload by reading
  the tool response instead of reading runtime source code.

### 3. Main-Path Slimming And De-Prompting

After executable context and structured feedback exist, remove or shrink
main-path wording and validation that only exists to compensate for missing
runtime signals.

Targets:

- keep `AGENTS.md` as a short framework-level runtime spec
- move repeated permission, payload, evidence, and receipt guidance into
  structured `prepare` context or tool feedback
- reduce static string validation in `runtime_agents.py` to framework-level
  invariants rather than task or payload explanations
- remove duplicate prompt-like wording from buddy contracts and shared skill
  runtime docs once the runtime output carries the same information
- simplify broker/direct duplicated main-path logic only where tests prove the
  product-mode behavior remains clearer

Acceptance signal:

- `AGENTS.md` does not grow and preferably becomes shorter.
- Tests assert structured env/tool signals, not long fixed prompt strings.
- Behavior constraints come primarily from env profiles, `prepare`, broker,
  `persist`, and browser evidence feedback.

## Explicitly Deferred

Do not add a continuation product UX such as:

```text
instance continue --from <receipt-or-run-or-track> --buddy market
instance open-handoff <track-id> --buddy design
```

That path may be useful later, but it is currently over-optimization and a
product requirement design task. The current iteration should improve the
existing main loop instead of adding a new user-facing flow.

## Durable Context, Not Prompt Bloat

"More context" should mean executable and durable context, not a larger generic
prompt.

Good context surfaces:

- current task and track summary
- artifact index and artifact summaries
- relevant receipts and prior run summaries when already in current context
- previous handoff metadata when already in current context
- active skill ids and compact runtime capabilities
- explicit read/write and tool boundaries
- structured runtime errors and next actions

Bad context surfaces:

- repeated generic guidance
- long methodology text
- hidden conventions that only exist in source code
- case-specific prompt patches

## Acceptance Signal For The Next Iteration

The next iteration is moving in the right direction if a normal buddy run shows
these properties:

- The buddy uses `prepare` first and receives enough task/track/artifact context
  to choose the correct path.
- The buddy reads executable `prepare` context and tool feedback instead of
  runtime source code to infer contracts.
- Tool errors produce safe stop/report behavior instead of self-bypass or
  self-escalation.
- Market research cannot silently bypass browser-native evidence requirements.
- PM product definition work naturally produces PRD, track state, and handoff
  instead of drifting into implementation.
- `AGENTS.md` remains framework-level and does not grow into task-specific
  prompt guidance.

## Conclusion

The environment tool layer iteration did not go in the wrong direction. It
completed the first necessary step: stronger executed boundaries and tool
permissions.

The next bottleneck is not another narrow permission patch or a new product UX
flow. The next bottleneck is main-path context and tool feedback
productization: make the correct buddy path visible, bound, executable, and
recoverable through existing runtime tools and durable receipt/handoff state.
