# Dev Landing Page Multi-Demand Real-Actor Acceptance Design

**Status:** approved experiment shape; written specification awaiting final
review before runtime execution.
**Date:** 2026-07-21
**Scope:** runtime observation only. Do not change Demand Sys, Task Sys, Track
Sys, daemon, or actor contracts during this experiment.

## 1. Why this run exists

The previous Market acceptance exposed a current-system fact:

```text
Demand A becomes terminal
        ↓ later related inbound information
Demand B starts as a new live root
```

Current Demand Sys does not reopen terminal Demands. The question is not yet
whether this is a defect. The immediate question is whether an immutable
terminal record plus a fresh live root is operationally effective in real
multi-step product work, and what information or coordination is lost when it
is effective only through external context such as source code or artifacts.

This run uses one real landing page implementation to compare three distinct
events that should not be assumed to share one relation meaning:

1. a supplement arriving while the initial Task is active;
2. a correction discovered after the initial Demand is completed;
3. a new, separately deliverable capability requested after the correction.

The run observes current behavior before proposing any lifecycle or relation
change.

## 2. Confirmed current semantics

The implementation establishes these baseline facts:

- `complete` and `cancel` terminalize a live Demand;
- no public Demand action clears `terminal` or reopens a Demand;
- `revise`, `split`, `set_parent`, and dependency mutation require a live
  subject;
- `set_parent` and dependency creation require a live relation target;
- `absorb_into`, `mark_duplicate`, and `supersede` require a live target;
- Demand Check exposes unchecked revisions plus a compact **live** index, not a
  terminal-history matching index;
- a terminal Demand can preserve lineage that was established while the
  relevant target was live, but a later Demand cannot retroactively establish
  a live-structure edge to it.

Therefore the present runtime does **not** perform:

```text
completed → reopened live → reorganized
```

It performs:

```text
completed record remains immutable
new inbound need → new live Demand → independent organization and Task choice
```

## 3. Hypotheses, not decisions

The experiment must distinguish these competing explanations.

### H1 — Frozen terminal plus new root is sufficient

The prior Demand is genuinely satisfied. A later related need can be executed
correctly from the current source, artifact, Track, and message context. Demand
relations need only coordinate live work.

Evidence supporting H1 would include correct continuation without repeated
discovery, loss of acceptance constraints, duplicated implementation, or wrong
Task selection.

### H2 — The original Demand was completed too early

A post-delivery correction may show that the original satisfaction judgment was
wrong or too coarse. The missing capability may be better completion review,
reopening, or revision semantics rather than a cross-terminal parent edge.

Evidence supporting H2 would include a correction that invalidates the original
acceptance evidence or shows the page never met A's stated criteria.

### H3 — New work is legitimate but needs historical/semantic lineage

The original Demand remains correctly completed, while a later need is a new
deliverable derived from it. Execution can proceed as a new root, but the system
may lose why the new work exists, which prior result it extends, or how several
Demands form one engagement.

Evidence supporting H3 would include correct code execution alongside missing
Demand-level continuity, repeated context reconstruction, or inability to
inspect the engagement as one need structure.

### H4 — One relation model is carrying two jobs

Live parent/dependency edges may be execution-coordination structure, while
post-terminal continuity may be immutable provenance or lineage. The run may
show these concerns should remain separate rather than weakening every live
relation invariant.

This is only a candidate interpretation. No new relation type is designed in
this memo.

## 4. Real environment and authority path

The run uses the default BuddySwitch environment:

```text
/Users/chen/.codex-buddyswitch
```

All actor lifecycle and interaction operations use the formal public CLI:

```text
./buddyswitch-codex instance start/status/input/stop/delete
./buddyswitch-codex demand list/get
./buddyswitch-codex task list/get
```

Runtime facts at design time:

- `instance list` is empty;
- browser ownership is inactive;
- the shared project workspace has not yet been initialized;
- starting the first actor will seed the launcher-owned project workspace from
  the repository `projects/app` mount point, which currently contains only its
  mount README;
- the initial request explicitly authorizes creation of a new app, so the Dev
  role's `readme_only` scaffold path is valid.

Business state mutations must come only from normal IM, actor decisions, and
the owning BuddySwitch tools. The controller must not write Demand, Task, IM,
artifact, Track, or daemon projections directly. App-server transcript reads or
owned projections are fallback evidence only when a public CLI read cannot
expose the required observation.

## 5. Actors and model configuration

Create two real actors through the default CLI:

- one PM actor used only to dispatch realistic IM messages and perform final
  product review;
- one Dev actor that owns Demand checks, Task choices, source edits, local
  verification, and implementation reporting.

Use lower-latency model depth:

- PM parent and side: `fast`;
- Dev parent: `balanced`;
- Dev side: `fast`.

No fake Codex executable, direct Demand construction, controller-selected
relation action, or pre-seeded Task is allowed.

## 6. Product brief

The fictional product is **FluxOps AI**, an AI data-operations tool for data
platform teams. It detects pipeline incidents, groups symptoms, explains likely
root causes, and guides safe recovery.

The experiment creates a new responsive single-page landing page under the
launcher-owned `projects/app` source root. The implementation must be locally
runnable and visibly testable. The Dev actor chooses the smallest appropriate
frontend stack from the empty/readme-only source state rather than receiving a
controller-selected framework.

## 7. Natural lifecycle sequence

The controller does not name Demand ids or actions in any business message.

### A — Initial deliverable

PM sends Dev a request to build the first runnable FluxOps AI landing page. The
page must communicate the problem, product mechanism, primary workflow, proof
boundary, and one clear conversion action; it must work on desktop and mobile.

The request explicitly permits scaffolding a new app and asks Dev to verify the
real rendered page. The controller catches the resulting Demand and active Task
before sending B.

### B — In-flight supplement to the same deliverable

While A's Task is active, PM adds that the page must make incident investigation
concrete through an observable pipeline/incident timeline and root-cause view,
avoid generic AI imagery, and keep the result within the same landing-page
delivery rather than produce a second page.

Expected observation, not an instructed outcome: Dev should compare B with the
live A and decide whether to absorb, relate, queue, or retain it separately. The
run samples active Tasks to test the single-active gate.

### C — Post-completion correction selected from the actual page

After A is completed, the controller renders and inspects the real page at
desktop and mobile sizes. It selects one correction from the first observed
problem in this order:

1. broken layout, overflow, inaccessible interaction, or runtime error;
2. unreadable contrast or hierarchy;
3. a requested product mechanism missing or visually unclear;
4. CTA behavior or navigation that does not work;
5. a material claim presented more strongly than the page can support.

PM sends one concrete correction quoting the visible problem. The message says
only that the delivered page must be corrected; it does not tell Dev whether A
was incomplete, B should be absorbed, or a new Demand should supersede another.

This stage tests whether terminal immutability works for escaped defects or
instead exposes premature Demand completion.

### D — New related but independently deliverable capability

After C is resolved, PM requests an interactive **incident-cost estimator** on
the existing page. It must take a small set of understandable operational inputs
and produce an estimated monthly incident cost and recoverable opportunity. It
is a new conversion capability built on the existing page, not a rewrite of A
and not merely a correction.

This stage tests whether a fresh root is operationally adequate for legitimate
extension work and whether missing Demand lineage matters even when source-code
continuity is sufficient.

## 8. Visual and runtime proof

At A, C, and D boundaries, inspect the actual rendered page rather than relying
on source existence or actor summaries. Capture:

- desktop and mobile screenshots or equivalent browser evidence;
- runtime console/page errors;
- visible satisfaction of the applicable request;
- the source diff or file identity that produced that rendering;
- the Demand revision/check state and exact Task DemandRef active at the time.

The accepted browser visual companion may present actual page states or
side-by-side comparisons. It must not substitute a mockup for the implemented
page.

## 9. Observations to record

For A/B/C/D, record:

- IM id and delivery/daemon handling;
- Demand id, revision, checked revision, live/terminal state, parent,
  dependencies, and terminal lineage;
- the actor's stated matching/organization judgment;
- Task id, exact DemandRef basis revision, lifecycle timestamps, and maximum
  observed active count;
- source files changed, verification command, rendered result, and cleanup;
- whether the actor reconstructed prior context correctly without a Demand edge;
- whether a post-completion message invalidated earlier acceptance or introduced
  a genuinely new acceptance contract.

## 10. Interpretation rules

Do not treat one successful page update as proof that terminal-only relations
are sufficient. Judge separately:

1. **Execution correctness:** did Dev make the right change?
2. **Context continuity:** did it understand the prior deliverable without
   redundant or missing work?
3. **Demand organization:** does the stored state explain why the work exists?
4. **Coordination value:** would the state support prioritization or multiple
   simultaneous related needs?
5. **Completion validity:** was A actually satisfied when it became terminal?

After the run, classify C and D independently. Only then return to the design
question:

- retain live-only relations unchanged;
- strengthen completion/reopen behavior;
- add immutable cross-terminal provenance/lineage;
- or separate execution relations from historical/semantic relations.

The run may support more than one conclusion. It must not force all later
related needs into one mechanism.

## 11. Stop and cleanup policy

Do not reset the default environment automatically. It is the authorized real
environment and the generated page must remain available long enough for visual
review and evidence capture.

After evidence is complete:

- stop and delete only the exact PM and Dev actor instances;
- stop any page server and release browser ownership;
- report remaining default project and Demand/Task data explicitly;
- ask before destructive environment reset or project deletion.

## 12. Acceptance boundary

The experiment is complete only when:

- all four message stages have been exercised through real PM → Dev inbound
  delivery;
- no controller-directed Demand relation action was used;
- every page stage has rendered proof;
- Demand/Task state and actor reasoning have been captured;
- C and D have been separately interpreted against H1–H4;
- exact actor and process cleanup is proved;
- the final memo resumes the open relation-design question without declaring a
  fix from insufficient evidence.
