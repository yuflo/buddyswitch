# Phase 04: Remove Serial Semantics And Live-Surface Residue

Date: 2026-06-30

## Stage Goal

Ensure live code, tests, and current runbooks describe the rebuilt contract:

```text
iMessage control input remains prompt while actor replies are delivered asynchronously.
```

Historical memos and the current execution docs may mention old behavior only as explicitly replaced evidence. User-facing/current runbooks must not teach the old serial reply-wait model.

## Involved Files

Modify:

- `tests/test_imessage_channel.py`
- `docs/spec/imessage-channel-smoke-runbook.md`
- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-04-residue-live-surface.md`

Do not modify:

- Central IM service behavior.
- iMessage worker behavior except if residue tests expose a missed serial path.

## Current Evidence

- Code now has `run_forever()` as inbound loop and `run_outbound_forever()` as outbound loop in `tools/launcher/imessage_channel.py`.
- Focused scan excluding the current execution docs already has no stale serial hits:

```bash
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|handle_inbound_message\\(row\\).*poll_outbound_once|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S -g '!docs/spec/imessage-channel-im-api-boundary-optimization/**'
```

Result before Phase 4 edits: no hits.

- `docs/spec/imessage-channel-smoke-runbook.md` still documents the older normal flow and A/B isolation, but it does not include the delayed-control regression scenario from the memo.

## Target Behavior

- Residue tests prove `ImessageChannelWorker.run_forever()` does not call `poll_outbound_once()` after each inbound row.
- Residue tests scan live surfaces for stale serial reply-wait wording.
- The smoke runbook includes:
  - send normal actor message;
  - immediately send `/actors`;
  - actor list returns promptly;
  - original actor reply still arrives once in the same chat;
  - Web/imsg process cleanup evidence if live smoke is run.

## Test Plan

### 1. Worker source no longer has serial inbound/outbound loop

Add or extend `tests/test_imessage_channel.py::ImessageChannelResidueTests`.

Expected assertions:

- Source contains `run_outbound_forever`.
- Source does not contain `handle_inbound_message(row)` followed by `poll_outbound_once(...)` in the same loop.

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
```

### 2. Live-surface stale wording scan

Add a residue test that scans:

- `tools/launcher`
- `tests`
- `docs/spec`, excluding `docs/spec/imessage-channel-im-api-boundary-optimization/**`

Patterns:

```text
poll_outbound_once\(wait_ms=.*reply_wait_ms
handle_inbound_message\(row\).*poll_outbound_once
waits? for the actor reply before
serial iMessage
```

Expected result: no hits.

### 3. Smoke runbook covers delayed-control regression

Add a residue test asserting `docs/spec/imessage-channel-smoke-runbook.md` contains the current contract:

```text
Immediately send /actors before the actor reply arrives.
Confirm the actor list returns promptly.
Confirm the original actor reply still arrives once in the same chat.
```

Expected failure before docs update:

```text
AssertionError: delayed-control smoke step is missing
```

## Stage Acceptance

Phase 4 is complete only when:

- Residue tests fail for the expected missing runbook coverage before the runbook edit.
- Runbook is updated.
- Focused residue tests pass:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
```

- Manual scan returns no stale live-surface hits:

```bash
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|handle_inbound_message\\(row\\).*poll_outbound_once|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S -g '!docs/spec/imessage-channel-im-api-boundary-optimization/**'
```

## Risks

- Current execution docs intentionally mention old behavior as pre-implementation evidence. The residue scan excludes those docs to avoid treating process history as user-facing stale guidance.
- Manual live smoke remains optional until final acceptance because automated tests cover the delayed-control contract without starting long-lived services.

## Verification Log

RED, before runbook update:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
```

Result:

```text
2 failed, 4 passed
```

Expected failure causes observed:

- Smoke runbook did not include the delayed-control regression scenario.
- Residue scan initially matched its own stale phrase pattern literal; the test was adjusted to avoid self-hits while keeping the scan term.

GREEN, focused residue tests:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
```

Result:

```text
6 passed in 0.11s
```

Manual residue scan:

```bash
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|handle_inbound_message\\(row\\).*poll_outbound_once|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S -g '!docs/spec/imessage-channel-im-api-boundary-optimization/**'
```

Result: no hits.

Full iMessage channel suite:

```bash
python3 -m pytest -q tests/test_imessage_channel.py
```

Result:

```text
26 passed in 0.23s
```
