# Host Autonomy, Context, And Handoff Discovery Memo

Date: 2026-05-11
Scope: BuddySwitch product-mode runtime context, env tool descriptions, handoff discovery, and host decision quality.

## Core Question

Given an ordinary Market request such as:

```text
Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design. Follow runtime feedback when browser evidence is needed.
```

why should the Market host know how to find the PM handoff without the user teaching it the implementation path?

The answer should not be "because the prompt tells it to list tracks." The answer should be:

BuddySwitch exposes enough product context, tool affordances, descriptions, and structured feedback for the Codex CLI host to infer the next action.

## Product Principle

BuddySwitch should avoid adding hidden routing rules, workflow engines, handoff inboxes, automatic track binding, or prompt-level process recipes as the default response to host confusion.

The product direction is:

- runtime provides observable state and capability descriptions;
- env tools expose concise, domain-shaped operations;
- tool responses provide structured feedback and allowed next actions;
- the host decides what to inspect or mutate next;
- product prompts state goals and acceptance constraints, not internal procedures.

This keeps BuddySwitch as an environment and coordination layer, not a rule-heavy agent orchestrator.

## Current Runtime Model

PM handoff is stored as part of a committed buddy run audit under:

```text
buddyswitch/content/runs/<run-id>.json
```

That handoff becomes visible to later buddies only through context projection:

- `prepare` builds `track_context` when the active instance is bound to a track.
- `track_context.recent_handoffs` scans run audits for handoffs on that same track.
- `runtime_context.current_context_summary.recent_handoffs` provides a compact host-readable summary.
- `runtime_context.context_sources_desc` describes where request, task, artifact, track, and handoff context live.

If a Market instance is already bound to the relevant track, the host should read the prepared context and see the PM handoff directly.

If a Market instance is not bound to a track, the host must infer that it should inspect readable tracks, because:

- the user requested a handoff-driven continuation;
- handoff context is described as track context;
- `track-manager` exposes readable tracks and active-buddy task linkage;
- `context-manager` can summarize only the current binding;
- `handoff-manager` validates outgoing handoffs, but is not a discovery surface.

This inference should come from runtime descriptions and feedback, not from user-authored implementation instructions.

## What We Should Not Add By Default

Do not add these as the first fix:

- a first-class handoff inbox;
- automatic natural-language-to-track binding;
- a special Market handoff router;
- a rule that always lists tracks before Market work;
- hardcoded onboarding rewrite or next-buddy matching logic;
- long prompt recipes that tell the host every step.

Those are runtime policy additions. They reduce host autonomy and move BuddySwitch toward workflow orchestration before the context-and-feedback loop has been proven insufficient.

## Better Improvement Direction

Improve the environment's self-description and feedback quality while preserving host choice.

Useful improvements should look like:

- `context_sources_desc` clearly states that handoff context is projected through current track context.
- `current_context_summary` makes the absence of current track/task binding obvious.
- `track_manager.scope` and `track.list` feedback make readable tracks discoverable as candidate collaboration context.
- Track summaries include enough product fields for host selection: `title`, `summary`, `current_buddy`, `next_buddy`, `task_ids`, and status.
- `handoff_manager` description makes clear that it validates outgoing handoff payloads and is not the discovery mechanism.
- Tool rejection payloads point to context/tool surfaces, not hidden internal paths.

These are descriptions and feedback surfaces, not new workflow rules.

## Product Acceptance Thought Experiment

The Market prompt should stay goal-oriented:

```text
Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design. Follow runtime feedback when browser evidence is needed.
```

Expected host behavior:

1. Read prepared runtime context first.
2. If current track context includes a relevant PM handoff, use it.
3. If no track is bound, use available env tool descriptions and feedback to inspect readable tracks.
4. Select a relevant track based on product-visible fields such as title, summary, current buddy, next buddy, and recent handoff context.
5. Create or bind Market-owned task work only after the relevant collaboration context is identified.
6. Produce a Market-owned artifact and outgoing handoff.

This is a reasoning expectation for the host, not a mandatory scripted flow.

## Next Work After Context Reset

After `/clear`, restart from this memo and inspect the current implementation before changing anything.

Recommended next investigation:

1. Run a product-mode Market flow with the goal-oriented prompt and observe whether the host discovers the PM handoff without being told to list tracks.
2. Inspect the actual `prepare.runtime_context` payload shown to Market when:
   - the Market instance is already bound to the PM track;
   - the Market instance is fresh and has no current track binding.
3. Inspect `track.list`, `context.summarize`, and `handoff.validate` success/rejection payloads for decision quality.
4. Identify whether any missing clue is a context/description/feedback gap.
5. Only if context and feedback are provably insufficient after real product trials, discuss whether a new product concept is justified.

## Success Criterion

This thread is not about forcing Market to follow one prescribed path.

It is successful when a competent Codex CLI host can, from the runtime environment alone, infer how to locate relevant handoff context and continue work while respecting active-buddy ownership and env tool boundaries.

