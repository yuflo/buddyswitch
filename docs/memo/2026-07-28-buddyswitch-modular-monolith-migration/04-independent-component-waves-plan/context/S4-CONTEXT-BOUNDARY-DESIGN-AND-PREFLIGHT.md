# S4 Context Boundary Design and Preflight

> Decision: `SELECTED AND PREFLIGHTED`
> Reproducible probe: `S4CONTEXTP-20260804-02`

## 1. Bottleneck

Context behavior already composes accepted Public reads, but its files are
still dynamically discovered under a shared technical root and three pieces
of Context-only policy/projection remain on the shared `ToolContext`. The lane
must make Context independently owned without turning S4 into S5.

## 2. Considered designs

### A. Move only the three old files

Add a passive module and delete the old package, while leaving
`RuntimeObjectAccess`, `RegistryCatalogAccess` and
`runtime_policy_preview(...)` on `ToolContext`.

Rejected: physical ownership would change, but Context-specific behavior
would still have a shared-host owner. This fails the S4 acceptance sentence.

### B. Converge all of ToolContext now

Move or inject ActorPrivate, Browser, directory, signal, repo/domain and every
remaining host fact while moving Context.

Rejected: this is S5 Foundation convergence, expands the proof surface, and
risks changing accepted component behavior. Context does not need it.

### C. Direct Context projection module plus exact residue removal

Move the Context Tool/projection into one private module, explicitly select it
last, delete the old package, and remove only the three Context-only
`ToolContext` surfaces. Context Private invokes the existing generic Role
authorization projection directly from host facts.

Selected: it is the smallest complete owner-correct cutover. It leaves S5 a
clean, exact foundation list and introduces no new contract.

## 3. Final topology

```text
Application composition
  -> Context ModuleAssembly (last)
       -> ToolRegistration(context)
            -> Context Private projection
                 -> Track Public
                 -> Task Public
                 -> Artifact Public
                 -> Communication Public
                 -> generic Tool registry / Role auth / runtime profile
                 -> host ToolContext facts
```

There is one write-free Context Tool and no reverse dependency from an
accepted component to Context.

## 4. Representative final-topology probe

The second pre-handoff audit re-ran the probe using the exact command recorded
in `S4-CONTEXT-PRE-HANDOFF-AUDIT.md`. It constructed the proposed passive Context assembly from the current
`DEFINITION` and `invoke`, appended it last to the real component tuple and
used the real application builder and registry.

Observed:

```text
module order:
  demand, task, search, artifact, track, evidence, communication, context

daemon order:
  demand_triage, task_goal, demand_orchestration

Context Tool registrations:
  1

old discovery plus explicit Context:
  "tool 'context' is both explicitly registered and package-discovered"

simulated old-package absence plus explicit Context list_sources dispatch:
  PASS
```

The initial probe attempt, `S4CONTEXTP-20260804-00`, stopped while loading the
real Manifest because it had not projected application Skill exports first.
It made no source or external-state change. The accepted probe added the same
`configure_skill_exports(application.skills)` step used by application
activation, then passed. This confirms the mechanism against the declared
runtime rather than a partial mock. The review rerun
`S4CONTEXTP-20260804-02` reproduced the same positive and negative result and
left no repository or persistent runtime state.

## 5. Consequences

- old package deletion and new explicit registration are atomic;
- no compatibility re-export is possible or needed;
- Context is last because it consumes the accepted Public graph;
- Context owns the only exact global-order assertion;
- other component proofs stop copying the full component list;
- root tests remain root because they cross component/runtime boundaries;
- registry package discovery remains temporarily as an empty/probe-capable S5
  residue, not as a live product Tool owner;
- after Context accepts, S4 may close and S5 receives an exact host/scanner
  convergence list.
