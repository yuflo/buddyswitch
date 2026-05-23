# Codex App-server Service Mode Plan Review

Date: 2026-05-23

## Review Scope

Reviewed:

- `docs/spec/2026-05-23-codex-app-server-service-mode-objective.md`
- `docs/spec/2026-05-23-codex-app-server-service-mode-test-plan.md`
- `docs/spec/2026-05-23-codex-app-server-service-mode-development-plan.md`

The review checks that the plan is complete, forward-only, testable, and aligned with the user feedback.

## Source Re-check

BuddySwitch source checked:

- `buddyswitch-codex`
- `tools/launcher/instance.sh`
- `tools/launcher/env.sh`
- `tools/launcher/runtime_broker.sh`
- `tools/launcher/browser_cockpit.sh`
- `tools/launcher/cleanup.sh`
- `tools/launcher/codex_config.py`
- `tests/test_buddyswitch_launcher.py`

Codex source checked:

- `/Users/chen/Dev/codex/codex-rs/app-server/README.md`
- `/Users/chen/Dev/codex/codex-rs/app-server-protocol/src/protocol/common.rs`
- `/Users/chen/Dev/codex/codex-rs/app-server-protocol/src/protocol/v2/thread.rs`
- `/Users/chen/Dev/codex/codex-rs/app-server-protocol/src/protocol/v2/turn.rs`
- `/Users/chen/Dev/codex/codex-rs/cli/src/main.rs`

Local command checks:

- `codex app-server --help`
- `codex resume --help`
- Python dependency probe for `websocket` and `websockets`

Result: no third-party Python WebSocket dependency is available by default, so the plan correctly requires a Python standard-library WebSocket-over-UDS client.

## Completeness Check

Covered:

- service start
- service input
- active turn steering
- attach
- stop
- status/list
- interrupt
- delete/reset/cleanup active guards
- browser lifecycle
- runtime broker lifecycle
- Codex config reuse
- old public path removal
- protocol client tests
- launcher behavior tests
- focused and optional smoke verification

Not included by design:

- co-work daemon
- message system redesign
- shared co-work task/task-list
- Codex source changes
- old TUI compatibility path

This matches the requested phase boundary.

## Forward-only Check

The plan explicitly removes or rejects:

- `instance open`
- `instance start --buddy <buddy> -- <codex args...>`
- launcher marker active truth
- TUI exit as service lifecycle end
- separate public `send` and `steer` commands

No compatibility bridge is planned for the old main path.

## Test Quality Check

The test plan is requirement-first:

- requirements are named as FR1-FR15
- every requirement maps to tests
- protocol tests cover external Codex contract behavior
- launcher tests assert user-visible state and command behavior
- fakes are constrained to app-server wire behavior and fake `codex` process capture

The plan avoids tests that only assert private function calls or let both old/new paths pass.

## Ambiguity Check

Resolved:

- `attach` means TUI remote resume, not service start.
- `input` is the only user-facing send command.
- active turn id is queried from app-server, not trusted from local JSON.
- service health replaces launcher marker health.
- browser stop is part of service stop.
- `codex app-server daemon` is not used.
- `codex app-server proxy` is not used as JSONL.

Resolved implementation ownership:

- Shell helpers update `instance.json`.
- `tools/launcher/app_server.py` updates only app-server runtime files and returns structured JSON results.
- This keeps the instance record mutation model aligned with existing `tools/launcher/env.sh` helpers.

## Risk Review

High-risk area:

- Python WebSocket-over-UDS client.

Mitigation:

- implement it as a small isolated module in `tools/launcher/app_server.py`
- cover handshake, frame handling, timeouts, notifications, and JSON-RPC errors with focused tests before wiring launcher lifecycle

Medium-risk area:

- replacing many existing `instance_open_*` tests.

Mitigation:

- do not bulk-delete tests blindly
- rewrite tests around the equivalent service-mode behavior: start, attach, input, stop, active guards

Low-risk area:

- Codex config patching.

Mitigation:

- keep `tools/launcher/codex_config.py` as the single config source and only verify app-server inherits the same instance `CODEX_HOME`

## Review Conclusion

The plan is complete enough to hand to implementation. It stays within the first phase, removes old paths instead of layering compatibility, and defines enough tests to prevent a superficial migration.
