# Switch Command Residue Cleanup Memo

## Goal

Remove the remaining special-case handling for old switch command-shaped input.
After cleanup, text such as `switch pm: ...`, `switch dev: ...`, and `switch market: ...` is ordinary `request_text`.
It must not trigger router behavior, and it must not be rejected only because it resembles retired switch syntax.

The active buddy remains authoritative from locked instance metadata, not from user text.

## Current Residue

- Runtime residue:
  - `scripts/turn_runtime.py::_is_legacy_command_shaped_request`
  - the `prepare` branch that returns `E_LEGACY_COMMAND_INPUT`
- Test residue:
  - `tests/test_turn_runtime.py::test_prepare_rejects_legacy_command_shaped_request_without_reservation`
- Spec residue:
  - `docs/spec/2026-05-06-buddy-run-persist-test-plan.md` still says legacy command-shaped requests remain rejected.

Do not change launcher top-level legacy CLI failures such as `buddyswitch-codex start`, `buddy`, `cleanup`, `reset`, `browser`, or `workspace`.
Those are separate public CLI cleanup guards and should still fail closed.

## Implementation Scope

1. Delete `_is_legacy_command_shaped_request` from `scripts/turn_runtime.py`.
2. Delete the `E_LEGACY_COMMAND_INPUT` branch from `_build_prepare_turn_context`.
3. Replace the rejection test with a positive prepare test:
   - input: `switch market: do competitor scan`
   - locked instance buddy: `pm`
   - expected: `ok=true`
   - expected: `active_buddy == "pm"`
   - expected: `request_text == "switch market: do competitor scan"`
   - expected: a run reservation is created like any ordinary request
4. Update the active test plan wording to say switch-prefixed text is ordinary request text.
5. Keep documentation and help surfaces from teaching `switch <buddy>:` as a command syntax.

## Acceptance Criteria

- `switch market: do competitor scan` prepares successfully in a `pm` instance.
- The request text is preserved exactly.
- Active buddy still comes only from launcher instance metadata.
- No switch parser, router, grammar contract, `recommended_switch`, or `reference_switches` field is reintroduced.
- Top-level retired launcher commands still fail closed before Codex is invoked.

## Verification

Run targeted tests:

```bash
python3 -m pytest tests/test_turn_runtime.py -k "switch_prefixed_text_as_ordinary_request or prepare"
python3 -m pytest tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -k "switch or legacy command or launcher_help"
```

Run residue scan:

```bash
rg -n "E_LEGACY_COMMAND_INPUT|_is_legacy_command_shaped_request|Legacy command-shaped request remains rejected" scripts tests docs
```

Expected residue scan result after implementation: no active runtime/test-plan matches for the retired rejection behavior.
