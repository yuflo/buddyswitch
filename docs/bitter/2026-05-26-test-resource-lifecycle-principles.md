# Test Resource Lifecycle Principles

Date: 2026-05-26
Status: distilled principle note from the launcher `/side` test resource exhaustion incident.

## Core Lesson

Any test that starts a persistent service is not a normal subprocess test.

If a test path can launch a daemon, app-server, browser, worker, watcher, broker, or detached process,
the test must own its full lifecycle before the suite is allowed to scale up.

Passing assertions are not enough. The test must also leave the host clean.

## What Went Wrong

The launcher `/side` work reused the real `instance start` path in integration tests.

That path intentionally starts long-lived runtime services:

- runtime broker;
- app-server;
- browser/fake browser process;
- fake Codex app-server.

The tests expanded from focused cases into a broad suite before proving that each started background
process was reliably registered and cleaned. Detached processes accumulated until the host reached
the process limit and could no longer start even a cleanup command.

This was a test harness lifecycle failure, not a `/side` product semantics failure.

## Non-Negotiable Rule

Before running broad verification, every service-starting test helper must have:

- explicit process registration;
- teardown that runs on assertion failure;
- pid or process-group based termination;
- escalation from graceful stop to force kill;
- cleanup of pid files, sockets, markers, and temporary runtime files;
- a post-run residual check.

If these are missing, do not run the large suite yet.

## Correct Validation Loop

Use this order for service-starting tests:

1. Add or inspect cleanup for the start helper.
2. Run one focused test.
3. Check residual processes and sockets.
4. Run the focused group repeatedly.
5. Check residuals again.
6. Only then run the broad suite.
7. After the broad suite, check residuals before declaring completion.

The verification target is:

```text
behavior passes + host resources return to baseline
```

## Process Handling Rules

For detached or long-lived processes:

- record pid and pgid when the process becomes visible;
- prefer terminating the process group when it is safe;
- never rely only on temporary directories or pid files that may disappear before cleanup;
- do not assume `subprocess.run()` returning means children are gone;
- treat browser/app-server/broker processes as owned resources, not incidental side effects.

## Warning Signs

Stop and inspect lifecycle if any of these appear:

- tests pass individually but fail in a long run;
- failures drift across unrelated tests;
- `fork: Resource temporarily unavailable`;
- `BlockingIOError: Resource temporarily unavailable`;
- missing capture files after a launcher start;
- repeated app-server, broker, fake Codex, or browser processes after tests finish.

These usually indicate resource leakage, not random flakiness.

## General Principle

Integration tests are allowed to use real product paths only when the harness is as disciplined as
the product lifecycle it exercises.

For long-lived services, cleanup is part of the test contract.

No lifecycle proof, no broad verification.
