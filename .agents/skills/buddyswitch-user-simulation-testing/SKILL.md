---
name: buddyswitch-user-simulation-testing
description: Use when Codex must turn a BuddySwitch feature memo, implementation memo, target behavior, or existing test result into a low-friction simulated-user test plan, run, audit, or evidence-backed stability report through Codex CLI.
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

## Optimization Goals

The skill should produce these effects:

1. Infer the feature's expected product effects from the memo, commit, or target claim before choosing scenarios.
2. Synthesize the means/gates/adapters from those effects instead of asking the user to preselect test mechanics.
3. Ask at most one compact correction/risk checkpoint before the run unless real authorization is required.
4. Use bounded sub-agents for independent read-heavy audits or isolated simulation surfaces when that shortens evidence collection.
5. Write every process note, plan, evidence file, temporary probe script, sub-agent output, cleanup proof, and final summary under the records root.
6. Keep the run strictly probe-only: report failures with evidence and suggested fix direction, but do not modify product code.

## Minimum Input

Best input:

```text
Use buddyswitch-user-simulation-testing on docs/memo/<feature-memo>.md
```

Optional overrides:

```text
Focus: <risk, commit, feature slice, or failure mode>
Mode: Design | Run | Audit | Extend
Records: <where all notes, plan, evidence, temporary scripts, sub-agent output, cleanup, and summary go>
Constraints: <fake-only, live required, no source edits, time box, preserve actors>
```

Target-only input is allowed when no memo exists. Infer the missing fields and state the coverage limit.

## Defaults

Use these unless the user says otherwise:

- `Mode`: `Design` for "plan"; `Run` for "test/verify/prove"; `Audit` for existing results; `Extend` for missing gates.
- `Records`: `docs/spec/<memo-or-target-slug>/evidence-<date>/`.
- `Codex`: fake Codex for deterministic host simulation unless the claim or user explicitly requires live Codex.
- `Browser`: in Codex CLI, default to Playwright/browser MCP for local/public page checks. Use Chrome DevTools MCP only when the claim needs CDP-specific evidence such as console, network, performance, DOM/style inspection, or concrete Chrome target state. Treat the Codex Chrome extension backend as unavailable in CLI unless `agent.browsers.list()` and `agent.browsers.get("extension")` prove it works in the current session. Use Desktop `@Chrome` / `chrome:control-chrome` only from Codex App/Desktop when signed-in Chrome profile state is part of the claim and the user explicitly authorizes it.
- `Source edits`: forbidden during simulation and audit.
- `Temporary scripts`: allowed only under the records root, usually `scripts/` or `subagents/<name>/scripts/`.
- `Cleanup`: stop/delete actors and clean run roots unless the user explicitly asks to preserve them.

Only ask before proceeding when product meaning is ambiguous or a risk confirmation is required.

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

1. Read the feature memo or target behavior.
2. If a memo is supplied, read `references/memo-to-goals.md` and extract 2-5 effects:
   - `P0 user effect`;
   - `P1 stability invariant`;
   - `P2 residue guard`;
   - `Out of scope`.
3. Run a strategy synthesis pass: map the inferred effects to required means families, gates, adapters, sub-agent candidates, and claim downgrades. Use:
   - `references/simulation-means.md` for performance means;
   - `references/gate-levels.md` for claim levels;
   - `references/scenario-matrix.md` for surface-specific scenarios;
   - `references/evidence-schema.md` before writing evidence.
4. Pick the smallest credible plan that can prove the effects. If a required means family or gate is skipped, record the downgrade before running.
5. Emit one correction checkpoint:

```markdown
## Simulation Checkpoint
I will prove:
- [P0/P1/P2] ...

I will use:
- Means: ...
- Gates: ...
- Sub-agents: yes/no, because ...
- Records: ...

I will not claim:
- ...

I will write only under:
- Records: ...

Proceeding unless this claim boundary is wrong.
```

6. If risk confirmation is required, wait. Otherwise continue in the selected mode.
7. Write a full plan under the records root.
8. In `Run` or `Extend`, execute the shortest credible gate first, then expand only where the confirmed effects require it.
9. Capture commands, screenshots if applicable, HTTP traces, state snapshots, logs, cleanup proof, sub-agent outputs, probe-only proof, and residual risks.
10. Report `FULL PASS`, `PARTIAL PASS`, `FAIL`, or `BLOCKED`.

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

Use the smallest gate set that covers the inferred effects:

- `G0 Contract`: code-level/API contracts only.
- `G1 Fake Product Simulation`: real launcher/daemon/runtime path with fake Codex.
- `G2 Entry Surface Simulation`: Web, IM wake, Track comment wake, CLI, or browser/cockpit surfaces.
- `G3 Stress And Recovery`: repeated use, concurrency, stop/resume, restart, stale state, cleanup failure.
- `G4 Live Codex Smoke`: real Codex app-server compatibility.

If a relevant gate is skipped, the final result cannot be `FULL PASS`.

## Strategy Synthesis

Infer required means from the effect language:

- lifecycle, lease, turn id, target, stale state, cross-actor, cleanup ownership -> `scripted-invocation` plus `state-log-audit`.
- stable, high-frequency, concurrent, restart, stop/resume, recovery, interrupt failure -> `stress-recovery-drive` and `G3`.
- Web, CLI, IM wake, Track comment wake, browser, cockpit, user entry -> `scripted-invocation` or `visible-operation` adapters under `G2`.
- visible UI, page state, browser operation -> `visible-operation`.
- live Codex, real service, signed-in browser profile, extension backend -> `live-dependency-smoke` and `G4`.
- remove, replace, converged, no old path, no fallback, no residue -> `static-residue-audit`.

User-provided surfaces are hints, not the source of truth. The source of truth is the product effect that must be proven. If an inferred required family cannot run, downgrade the claim explicitly and explain what remains unproven.

## Sub-Agent Use

In `Run`, `Audit`, and `Extend`, use bounded sub-agents by default when they can independently collect evidence without sharing mutable state. Good sub-agent splits:

- G2 has more than two independent surfaces, such as Web, IM wake, and Track comment wake.
- Static residue audit can run in parallel with runtime simulation.
- Log/state review can run after a scenario while the main agent prepares the next scenario.
- Stress/recovery and failure-analysis probes can run in isolated actor/run roots.

Each sub-agent must receive:

- exact effect/surface under test;
- records subdirectory, for example `subagents/web-side-lifecycle/`;
- probe-only boundary and source-edit ban;
- required command/evidence format;
- cleanup expectation for actors/resources it creates.

The main agent owns the final claim. If sub-agent tooling is unavailable, continue sequentially and record the downgrade as `subagent_not_available`, not as a product failure.

## Browser Capability Selection

Browser tools are adapters, not top-level means. First choose the means family:

- `visible-operation`: when the user-visible page or desktop behavior matters.
- `state-log-audit`: when console, network, DOM, target state, or browser manager logs prove internal behavior after an action.
- `live-dependency-smoke`: when signed-in Chrome profile, extension state, or real external browser state matters.

Then choose the adapter:

- Playwright/browser MCP by default for local/public CLI-run browser checks.
- Chrome DevTools MCP only for CDP-specific evidence: console, network, performance, DOM/style inspection, or concrete Chrome target state.
- Desktop `@Chrome` / `chrome:control-chrome` only when signed-in Chrome profile state is part of the claim, the Chrome backend works in the current Codex App/Desktop session, and the user explicitly authorizes it.
- Do not spend simulation time reinstalling Chrome/browser plugins when CLI reports `Browser is not available: extension`, `agent.browsers.list()` is empty, or logs show `untrusted-code-signing-identity`; record it as a CLI Chrome-backend limitation and use Playwright/browser MCP or Chrome DevTools MCP according to the claim.
- Computer Use only when the claim depends on human-like desktop GUI operation across apps. On macOS this requires Screen Recording and Accessibility permissions.

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
