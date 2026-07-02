# Gate Levels

Use these gates to decide what a BuddySwitch stability claim is allowed to say after feature effects are confirmed.

## Table Of Contents

- [G0 Contract](#g0-contract)
- [G1 Fake Product Simulation](#g1-fake-product-simulation)
- [G2 Entry Surface Simulation](#g2-entry-surface-simulation)
- [G3 Stress And Recovery](#g3-stress-and-recovery)
- [G4 Live Codex Smoke](#g4-live-codex-smoke)
- [Claim Rule](#claim-rule)

## G0 Contract

Purpose: prove code-level contracts.

Typical commands:

```bash
python -m unittest -q tests.test_side_thread_lifecycle
python -m unittest -q tests.test_task_sys_side_processing
python -m unittest -q tests.test_web_management
python -m unittest -q tests.test_im_wake_handler tests.test_track_comment_added_handler
```

Can claim:

- Contract-level behavior passed.

Cannot claim:

- User scenario stability.
- Live Codex compatibility.
- Multi-entry stability.

## G1 Fake Product Simulation

Purpose: prove user-like launcher, daemon, runtime broker, app-server socket, registry, and cleanup behavior with deterministic fake Codex.

Required:

- isolated `HOME` or `CODEX_HOME`;
- fake `codex` from `tests/helpers/fake_codex.py`;
- user-facing `./buddyswitch-codex instance ... --json` commands;
- command evidence;
- fake app-server state and call logs;
- log scan;
- cleanup proof.

Can claim:

- Fake-Codex product simulation passed for the tested surfaces.

Cannot claim:

- Live Codex protocol compatibility.

## G2 Entry Surface Simulation

Purpose: prove distinct user entrypoints that do not reduce to a single CLI path.

Surfaces:

- CLI input and side commands.
- Web management HTTP API.
- IM wake.
- Track comment wake.

Required:

- one scenario per claimed entrypoint;
- source payload and target actor evidence;
- status/log/state checks after wake or API action.

Can claim:

- Tested entrypoints passed under the declared Codex surface.

Cannot claim:

- Untested entrypoint stability.

## G3 Stress And Recovery

Purpose: prove target identity and lease behavior under repeated probing, concurrency, stop/resume, daemon restart, or failure injection.

Required assertions:

- no duplicate open side lease for the same target unless expected;
- no wrong actor mutation;
- no stale target steer;
- no unexplained runtime error;
- expected resume semantics are stated before testing.

Can claim:

- Stress or recovery stability for the tested conditions.

Cannot claim:

- Long-run soak or production stability unless those were tested.

## G4 Live Codex Smoke

Purpose: prove minimal compatibility with the real Codex app-server service.

Required:

- no fake `codex` in `PATH`;
- isolated BuddySwitch state root;
- real `codex app-server --listen` through BuddySwitch launcher;
- minimal start/status/side/send/close/stop/delete;
- logs and cleanup proof.

Can claim:

- Live Codex smoke passed for the minimal tested path.

Cannot claim:

- Model quality.
- Broad production stability.
- Multi-entry stability unless G2 also passed live.

## Claim Rule

The final claim is limited to the confirmed effects and highest required gate that passed. If a target-relevant required gate is skipped, failed, or blocked, downgrade the claim and never report `FULL PASS`. If a confirmed effect includes live service compatibility and G4 is skipped, the result is not `FULL PASS`.
