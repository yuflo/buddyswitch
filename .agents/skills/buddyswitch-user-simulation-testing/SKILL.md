---
name: buddyswitch-user-simulation-testing
description: "Use when Codex needs BuddySwitch probe-only simulated-user testing: plan, run, audit, or extend verification from a feature memo, implementation memo, target behavior, or existing evidence, with evidence-backed claim downgrade and stability limits."
---

# BuddySwitch User Simulation Testing

## Purpose

Turn a BuddySwitch feature memo into a short simulated-user SOP: infer what product effects matter, choose the smallest credible user-like test means, record evidence, and limit the final stability claim to what was actually proven.

This skill is probe-only. It exists to discover problems, reproduce behavior, collect evidence, and state stability limits. It must not implement product fixes or refactor BuddySwitch source.

## Core Principle

Do the thinking for the user. Do not turn this skill into a form or a two-approval workflow.

The normal path is:

```text
feature memo -> Codex infers effects + strategy -> one correction checkpoint
  -> full plan -> run/audit/report with evidence
```

The checkpoint is for correction, not ceremony. If the user already asked to run and no risk confirmation is needed, state the checkpoint and continue.

## Non-Negotiables

- Infer effects before selecting scenarios.
- Synthesize means families, gates, adapters, sub-agent candidates, and claim downgrades from effects.
- Ask at most one compact correction checkpoint unless Risk Confirmation applies.
- Write process notes, plan, evidence, temporary probe scripts, sub-agent output, cleanup proof, and summary under the records root.
- Keep the run probe-only: report failures with evidence and suggested fix direction, but do not modify product code.
- If a target-relevant required means family or required gate is skipped, failed, or blocked, downgrade the claim and never report `FULL PASS`.

## Reference Routing

- Read `references/invocation-and-pairing.md` first to infer mode, defaults, records path, sparse-input behavior, and the single checkpoint from the user's memo, target behavior, or existing evidence.
- Read `references/memo-to-goals.md` when a memo, implementation memo, PRD-style note, or broad target must be converted into P0/P1/P2 effects.
- Read `references/simulation-means.md` before choosing means families, concrete adapters, browser tools, live dependencies, stress/recovery probes, or static residue audits. When an effect mentions browser, Chrome, CDP, Playwright, profile, extension, Desktop, or Computer Use, read its Browser Adapter Notes before choosing tools.
- Read `references/gate-levels.md` before setting or auditing the strongest allowed claim.
- Read `references/scenario-matrix.md` when the target names CLI, Web, IM wake, Track comment wake, browser/cockpit, stress, or sub-agent-fit surfaces.
- Read `references/evidence-schema.md` before writing evidence or validating a pass/partial-pass claim.
- Read `references/buddy-runtime-surfaces.md` when planning BuddySwitch launcher, daemon, Web, IM, Track, browser/cockpit, fake Codex, or live Codex scenarios.

## Probe-Only Boundary

This skill may create evidence files and temporary probe scripts under the records root. It must not edit:

- product source under `projects/app/`, `buddyswitch/`, `tools/`, runtime contracts, launcher code, role guidance, or checked-in tests;
- `.agents/skills/**`, docs, or prompts unless the user's task is explicitly to improve this skill;
- runtime object files directly under `buddyswitch/objects/**` or private runtime paths.

If a simulation finds a bug, stop at evidence and diagnosis. Record the failing command, state/log proof, likely fix area, and next recommended debugging path. Do not patch the product in the same skill run.

Sub-agents inherit the same boundary. Their write access is limited to `Records/subagents/<name>/` plus their command outputs.

## Risk Confirmation

Stop and ask for explicit confirmation only when Codex would otherwise:

- run live Codex without the user explicitly asking for live coverage;
- use the user's signed-in Chrome profile, browser history, Desktop `@Chrome`, or Computer Use without the user explicitly asking for it;
- edit source code instead of only simulating/auditing;
- preserve actors, browser sessions, runtime roots, or other state after the run;
- delete or mutate user data beyond actors/resources created by the simulation;
- choose between two materially different product interpretations.

Do not stop just because `Focus`, `Mode`, `Records`, `Actors`, or `Surfaces` were omitted. Infer and record defaults.

## SOP

1. Read the user request plus the feature memo, target behavior, or existing evidence; read `references/invocation-and-pairing.md` for mode/defaults/checkpoint handling. Done when: user requirements, inferred mode, records root, fake/live policy, source-edit policy, and cleanup policy are recorded.
2. If a memo or broad target is supplied, read `references/memo-to-goals.md` and extract 2-5 effects. Done when: P0 user effects, P1 stability invariants, P2 residue guards, out-of-scope items, and source sections are recorded.
3. Run a strategy synthesis pass with `references/simulation-means.md`, `references/gate-levels.md`, and relevant scenario references. Done when: required means families, required gates, adapters, sub-agent candidates, and downgrade rules are recorded.
4. Pick the smallest credible plan that can prove the effects. Done when: each skipped target-relevant required means family or required gate has a written downgrade and the planned result cannot be `FULL PASS` if one is skipped.
5. Emit one correction checkpoint using `references/invocation-and-pairing.md`; wait only when Risk Confirmation applies. Done when: the checkpoint is recorded with effects, means, gates, sub-agent plan, records root, skipped claims, allowed write root, and `confirmed_by`.
6. Write the full simulation plan under the records root. Done when: `plan.md` covers user requirements, effects, strategy, scenarios, commands or audits, evidence paths, cleanup, and residual risks.
7. In `Run` or `Extend`, execute the shortest credible gate first, then expand only where confirmed effects require it. Done when: the first gate result, expansion reason, and any blocked/skipped gate downgrade are recorded.
8. Capture commands, screenshots if applicable, HTTP traces, state snapshots, logs, cleanup proof, sub-agent outputs, probe-only proof, and residual risks. Done when: every means family and adapter has evidence or an explicit blocked/skipped record.
9. Run `scripts/summarize_simulation_evidence.py` after evidence collection. Done when: summary validation is clean, or every validator issue is reflected in `BLOCKED`, `FAIL`, or a downgraded `PARTIAL PASS`.
10. Report `FULL PASS`, `PARTIAL PASS`, `FAIL`, or `BLOCKED` using the exact Report Format below. Done when: the final claim does not exceed passed gates/means and Remaining Risk names every skipped or weak gate.

## Operating Modes

- `Design`: checkpoint plus full simulation plan; no commands.
- `Run`: checkpoint, plan, execute, capture evidence, cleanup, report.
- `Audit`: map existing evidence to inferred effects and correct the claim.
- `Extend`: start from existing evidence and add missing gates only.

## Pair With

- Pair with `superpowers:brainstorming` only when there is no memo and the product outcome itself is still unclear.
- Pair with `superpowers:writing-plans` for a multi-step simulation plan.
- Pair with `superpowers:dispatching-parallel-agents` when independent surfaces need separate research or audit.
- Pair with `superpowers:systematic-debugging` when a scenario fails unexpectedly.
- Pair with `superpowers:verification-before-completion` before any pass/completion claim.
- Pair with `shape-html-artifact` when the user needs a visual review artifact for the SOP, examples, evidence, or coverage.
- Use `scripts/init_simulation_evidence.py` and `scripts/summarize_simulation_evidence.py` for standard evidence skeletons.

## Gate Selection

Use the smallest gate set that covers the inferred effects. See `references/gate-levels.md` for G0-G4 details.

If a target-relevant required means family or required gate is skipped, failed, or blocked, downgrade the claim and never report `FULL PASS`.

## Strategy Synthesis

User-provided surfaces are hints, not the source of truth. The source of truth is the product effect that must be proven.

Use `references/simulation-means.md` for effect-to-means rules and adapter selection. If an inferred required means family cannot run, downgrade the claim explicitly and explain what remains unproven.

## Sub-Agent Use

In `Run`, `Audit`, and `Extend`, use bounded sub-agents by default when they can independently collect evidence without sharing mutable state. Read `references/scenario-matrix.md` Sub-Agent Fit before splitting Web, IM, Track, static residue, log/state, stress, or recovery workstreams.

Each sub-agent must receive:

- exact effect/surface under test;
- records subdirectory, for example `subagents/web-side-lifecycle/`;
- probe-only boundary and source-edit ban;
- required command/evidence format;
- cleanup expectation for actors/resources it creates.

The main agent owns the final claim. If sub-agent tooling is unavailable, continue sequentially and record the downgrade as `subagent_not_available`, not as a product failure.

## Browser Capability Selection

Browser tools are adapters, not top-level means. When a claim mentions browser, Chrome, CDP, Playwright, profile, extension, Desktop, or Computer Use, read `references/simulation-means.md` Browser Adapter Notes before choosing tools. Do not claim browser/profile coverage beyond the available adapter and passed gates.

## BuddySwitch Constraints

- Drive scenarios through user-facing surfaces: `./buddyswitch-codex`, Web/browser UI, Web HTTP APIs, IM/Track wake paths, CLI browser MCP, Desktop `@Chrome` when authorized, browser/cockpit tools, or native env tools.
- Do not directly edit `buddyswitch/objects/**` or private runtime object paths.
- Use isolated `HOME`, `CODEX_HOME`, `BUDDYSWITCH_SHARED_ROOT`, and temporary run roots.
- Fake Codex is the deterministic default; live Codex must not have fake `codex` earlier in `PATH`.
- Stop and delete every actor created by the simulation unless preservation was explicitly requested.

## Required Evidence

A pass claim requires:

- user requirements/defaults record;
- memo analysis and inferred effects;
- strategy decision record with required means, gates, adapters, sub-agent plan, and downgrades;
- one correction checkpoint record;
- full simulation plan;
- family evidence and adapter evidence for each run means;
- `summary.json.means` with top-level means families and concrete adapters;
- `summary.json.probe_only` showing source edits were forbidden and writes stayed under the records root;
- sub-agent output records when sub-agents were used, or a recorded `subagent_not_available` downgrade when planned but unavailable;
- relevant state snapshots and logs;
- negative assertions for stale targets, wrong actors, forbidden old paths, and state pollution;
- cleanup proof;
- residual risk list.

Run `scripts/init_simulation_evidence.py` to create a standard evidence directory. Run `scripts/summarize_simulation_evidence.py` after collecting evidence to validate the summary.

## Report Format

Use this exact top-level structure:

```markdown
## Result
FULL PASS | PARTIAL PASS | FAIL | BLOCKED

## Effects Tested
[The inferred effects and any user correction.]

## Claim Proven
[One sentence. Must not exceed passed gates.]

## Means Used
[Means family plus adapter, for example scripted-invocation (CLI + IM message script), visible-operation (Chrome DevTools MCP), stress-recovery-drive.]

## Strategy
[Why these means/gates/adapters were required and which claims were downgraded.]

## Subagents
[Used/skipped/unavailable, with records paths and statuses.]

## Gates
[Gate table with required/run/status/evidence.]

## Evidence
[Paths to requirements, memo analysis, checkpoint, plan, commands, UI artifacts, logs, snapshots, summary.]

## Cleanup
[Stopped/deleted actors/resources and residue checks.]

## Remaining Risk
[Skipped or weak gates. Use "None" only when all required gates passed.]
```

## Unacceptable Conclusions

- "The memo is implemented because tests passed" without mapping tests to inferred user effects.
- "fake Codex simulation passed, so target stability is achieved."
- "unit tests passed, so live Codex is stable."
- "exit code 0" without status, logs, snapshots, and cleanup proof.
- "multi-entry stable" when only CLI was tested.
- "browser user behavior covered" when only static assets or unit tests were checked.
- "concurrency stable" when only one sequential send was tested.
- "live smoke skipped" while still claiming real-service stability.
- "problem fixed" when this skill only produced probe evidence.
