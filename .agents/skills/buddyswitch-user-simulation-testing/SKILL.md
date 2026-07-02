---
name: buddyswitch-user-simulation-testing
description: "Use when Codex needs BuddySwitch probe-only simulated-user testing from a feature memo, implementation memo, target behavior, or existing evidence, requiring a real user path, cleanup proof, and evidence-backed stability conclusion."
---

# BuddySwitch User Simulation Testing

## Purpose

The user may provide only a memo, target behavior, or existing evidence. Infer the real user effect, choose the smallest credible BuddySwitch user path, run or audit it, record evidence and cleanup proof, and interrupt only for real risk or semantic ambiguity.

This skill is probe-only. It discovers behavior, reproduces failures, collects evidence, and states a stability conclusion no stronger than the proof. It does not patch BuddySwitch product code.

## Default Behavior

Do the thinking for the user. Do not ask the user to choose mechanics, fill a form, approve a plan twice, or preselect internal test labels.

Accepted inputs:

- BuddySwitch feature or implementation memo;
- target behavior;
- existing evidence directory.

Defaults:

- If the user says verify, test, prove, or run, execute the smallest credible user path unless blocked.
- If the user supplies existing evidence, audit it against the same user-path proof rules and downgrade unsupported claims.
- Write notes and artifacts under `docs/spec/<slug>/evidence-<date>/` unless the user gives another records path.
- Source edits are forbidden during simulation.
- Fake, control-plane, unit, or static evidence may support diagnosis, but it is not user-path proof.

## Supporting References

- Read `references/memo-to-goals.md` only when a memo or broad target needs effect extraction.
- Read `references/buddy-runtime-surfaces.md` when choosing concrete BuddySwitch commands, surfaces, or runtime evidence.

## Probe-Only Boundary

Source edits are forbidden. This skill may write evidence under the records path, but it must not edit:

- product source under `projects/app/`, `buddyswitch/`, `tools/`, runtime contracts, launcher code, role guidance, or checked-in tests;
- runtime object files directly under `buddyswitch/objects/**` or private runtime paths;
- skill/docs/prompts, unless the user's task is explicitly to improve this skill.

If a simulation finds a bug, record the failing command, state/log/browser proof, likely fix area, and next debugging path. Do not fix the product in the same skill run.

## Interrupt Only For Risk

Continue without asking when missing fields can be inferred safely. Interrupt only when Codex would otherwise:

- run live Codex without explicit authorization;
- use signed-in Chrome, profile state, browser history, Desktop `@Chrome`, or Computer Use without explicit authorization;
- preserve actors, browser sessions, runtime roots, or other created state after the run;
- delete or mutate user data beyond resources created by the simulation;
- resolve material product meaning ambiguity without the user.

## Mandatory User Path

For verify/test/prove/run requests, run this path or record a concrete blocker before reporting:

```text
infer effect
  -> choose one user surface
  -> create actor or identify explicit target
  -> capture baseline status
  -> perform user entry action
  -> observe effect
  -> capture state/log/browser evidence
  -> clean up
  -> report bounded claim
```

For CLI-capable actor scenarios, start from the built-in BuddySwitch launcher path:

```bash
./buddyswitch-codex instance start --role <role> --json
./buddyswitch-codex instance status <actor-id> --json
./buddyswitch-codex instance input <actor-id> --text "<task>" --json
./buddyswitch-codex instance status <actor-id> --json
./buddyswitch-codex instance stop <actor-id> --json
./buddyswitch-codex instance delete <actor-id> --yes --json
```

Other valid user surfaces include Web UI/API, native env MCP from an actor runtime, cockpit MCP, IM wake, and Track comment wake. The report must show the actor/resource id or explicit target id and the command/tool that created, selected, or drove it.

## Browser And Cockpit Claims

Browser/cockpit user-path proof requires:

- actor/resource id;
- actor-facing browser/cockpit action;
- URL/page/target/screenshot evidence;
- state or log evidence;
- cleanup proof.

If any item is missing, the claim is `PARTIAL` or `BLOCKED`. Fake CDP, direct browser manager calls, unit tests, and static scans may support diagnosis, but they are not user-path proof by themselves.

## Minimal Evidence

A user-path claim must include:

- target effect inferred from input;
- primary user surface selected;
- actor/resource id or explicit target id;
- command/tool used for baseline status;
- command/tool used for user entry action;
- observed product effect;
- state/log/browser evidence path;
- cleanup result;
- source-edit/probe-only confirmation;
- claim limit and remaining risk.

If any required item is missing, the final report must say that user-path proof is incomplete.

## Claim Rule

Use only these report conclusions:

- `PASS`: target effect was proven through the required BuddySwitch user path and cleanup evidence.
- `PARTIAL`: some user-path evidence exists, but required proof is missing, weak, or downgraded.
- `FAIL`: the user path ran and contradicted the target behavior.
- `BLOCKED`: the required user path could not run.

If evidence is fake/control-plane/static-only, explicitly say it is not user-path proof.

## Report Format

```markdown
## Result
PASS | PARTIAL | FAIL | BLOCKED

## Effect Tested
[The inferred user effect.]

## User Path
[Surface, actor/resource id or explicit target id, entry action, and blocker if any.]

## Evidence
[Command outputs, state/log/browser/page artifacts, and evidence paths.]

## Cleanup
[Stopped/deleted actors/resources and residue result.]

## Claim Proven
[One sentence. Must not exceed the evidence.]

## Remaining Risk
[Missing or weak proof. Use "None" only when all required proof exists.]
```

## Unacceptable Conclusions

- "The memo is implemented because tests passed" without mapping tests to inferred user effects.
- "Fake/control-plane/static evidence passed, so user-path behavior is proven."
- "Browser user behavior covered" without actor-facing page, URL, target, or screenshot evidence.
- "Exit code 0" without status, observable effect, and cleanup proof.
- "Problem fixed" when this skill only produced probe evidence.
