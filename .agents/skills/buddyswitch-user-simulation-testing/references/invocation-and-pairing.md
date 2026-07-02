# Invocation And Pairing

This reference keeps user input small. Codex should infer defaults and ask only for risky or product-semantic ambiguity.

## Table Of Contents

- [Feature Memo Only](#feature-memo-only)
- [Optional Overrides](#optional-overrides)
- [Target-Only Fallback](#target-only-fallback)
- [One Checkpoint](#one-checkpoint)
- [Prompt Templates](#prompt-templates)
- [Pairings](#pairings)
- [Tooling](#tooling)
- [Defaults When Input Is Sparse](#defaults-when-input-is-sparse)

## Feature Memo Only

Preferred invocation:

```text
Use buddyswitch-user-simulation-testing on docs/memo/<feature-memo>.md
```

This is enough. Codex must infer effects, test means, gates, records path, actors, and cleanup defaults.

## Optional Overrides

Use these only when the user already knows the constraint:

```text
Focus: <risk, commit, feature slice, or failure mode>
Mode: Design | Run | Audit | Extend
Records: <where all notes, plan, evidence, cleanup, and summary go>
Constraints: <fake-only, live required, no source edits, time box, preserve actors>
```

Do not ask the user to fill these when reasonable defaults are available.

## Target-Only Fallback

When no memo exists:

```text
Target: <behavior or risk>
```

Optional:

```text
Claim: <strongest desired final statement>
Surfaces: <CLI | Web | IM wake | Track comment wake | browser/cockpit | live Codex | stress>
Records: <path>
Constraints: <scope/risk limits>
```

## One Checkpoint

Codex should normally send one correction checkpoint, not two approval gates.

```markdown
## Simulation Checkpoint
I will verify:
1. [P0] ...
2. [P1] ...
3. [P2] ...

I will use:
- Means: browser UI smoke, Web API trace, CLI fake-Codex lifecycle
- Gates: G1, G2, G3
- Records: docs/spec/<slug>/evidence-<date>

I will not claim:
- live Codex compatibility
- long-run production stability

Proceeding unless you want to change this.
```

Continue without waiting when all are true:

- the user asked to run/test/verify;
- no live Codex was newly inferred;
- no source edits are planned;
- cleanup only touches resources created by the simulation;
- no actors or runtime state will be preserved;
- the product effect is not ambiguous.

Wait for explicit confirmation only for Risk Confirmation conditions listed in `SKILL.md`.

Record the checkpoint in evidence with `confirmed_by`:

- `explicit_user_reply` when the user explicitly approves or edits the checkpoint;
- `stated_default_no_blocker` when Codex stated defaults and no risk condition required waiting;
- `user_requested_run` when the user already asked to run/test/verify and the checkpoint has no high-risk choice.

## Prompt Templates

### Minimal Run

```text
Use buddyswitch-user-simulation-testing on docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md
```

Expected Codex behavior:

- infer `Run` if the user says test/verify, otherwise `Design`;
- choose records path under `docs/spec/<memo-slug>/evidence-<date>/`;
- emit one checkpoint and continue unless risky;
- report with evidence and limits.

### Plan Only

```text
Use buddyswitch-user-simulation-testing on docs/memo/2026-07-02-browser-cockpit-control-plane-forward-rebuild-plan.md
Mode: Design
```

Expected output:

- inferred effects;
- means and gates;
- full plan;
- no command execution.

### Narrow Focus

```text
Use buddyswitch-user-simulation-testing on docs/memo/2026-07-01-side-thread-lifecycle-convergence-plan.md
Focus: repeated side-thread target stability and stop/resume behavior
Constraints: fake Codex first; live smoke only if needed for the final claim
```

Expected output:

- prioritize target identity, stale id, repeated send, stop/resume;
- name untested Web/IM/Track/live surfaces as remaining risk if skipped.

### Audit Existing Evidence

```text
Use buddyswitch-user-simulation-testing.
Mode: Audit
Feature memo: docs/memo/<feature-memo>.md
Records: <existing evidence directory>
```

Expected output:

- map existing evidence to inferred effects;
- classify claim as `FULL PASS`, `PARTIAL PASS`, `FAIL`, or `BLOCKED`;
- identify missing means/gates.

## Pairings

| Situation | Pair with | Why |
| --- | --- | --- |
| Product outcome unclear and no memo exists | `superpowers:brainstorming` | Clarify what the feature should achieve. |
| Multi-step simulation | `superpowers:writing-plans` | Turn checkpoint into a runnable plan. |
| Independent surfaces need research | `superpowers:dispatching-parallel-agents` | Split Web, CLI, IM/Track, browser/cockpit, live/stress inspection. |
| Scenario fails unexpectedly | `superpowers:systematic-debugging` | Diagnose before relaxing assertions or changing code. |
| Final pass/fail claim | `superpowers:verification-before-completion` | Prevent overclaiming. |
| User needs visual review | `shape-html-artifact` | Show SOP, examples, means, evidence, and limits spatially. |

## Tooling

| Need | Use |
| --- | --- |
| Evidence skeleton | `scripts/init_simulation_evidence.py` |
| Evidence summary validation | `scripts/summarize_simulation_evidence.py` |
| Memo goal extraction guide | `references/memo-to-goals.md` |
| Simulation means guide | `references/simulation-means.md` |
| Deterministic app-server | `tests/helpers/fake_codex.py` |
| Real user CLI | `./buddyswitch-codex instance ... --json` |
| Web entrypoint | `./buddyswitch-codex web`, `tools/launcher/web_management.py` HTTP API |
| Browser/cockpit entrypoint | browser cockpit proxy, CDP/browser runtime manager, search open-browser tool |

## Defaults When Input Is Sparse

If `Feature memo` is present:

1. Infer 2-5 effects.
2. Infer mode from wording.
3. Default records to `docs/spec/<memo-slug>/evidence-<date>/`.
4. Default constraints to fake Codex, isolated state, no source edits, cleanup required.
5. Emit one checkpoint and continue unless a risk condition requires confirmation.

If only `Target` is present:

1. Treat the target as the effect source.
2. Default surfaces to the smallest credible means, usually CLI/API/fake Codex.
3. State skipped live/multi-entry/stress means as residual risk.
