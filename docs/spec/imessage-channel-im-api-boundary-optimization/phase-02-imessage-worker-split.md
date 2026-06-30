# Phase 02: Split iMessage Worker Responsibilities

Date: 2026-06-30

## Stage Goal

Replace the serial iMessage worker loop with independent inbound and outbound loops sharing one controller and one stop lifecycle.

Target contract:

```text
Inbound loop:
  imsg.status()
  for row in imsg.watch_messages():
    controller.handle_inbound_message(row)

Outbound loop:
  while not stopped:
    controller.poll_outbound_once(wait_ms=DEFAULT_REPLY_WAIT_MS)
```

This phase fixes delayed control handling and late actor reply delivery. It does not yet add iMessage-side event ack-after-projection; that is Phase 3.

## Involved Files

Modify:

- `tools/launcher/imessage_channel.py`
- `tests/test_imessage_channel.py`
- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-02-imessage-worker-split.md`

Do not modify in this phase:

- `scripts/env/services/messages.py`
- `tools/launcher/external_im_session.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- Browser/Web UI assets.

## Current Code Evidence

- `tools/launcher/imessage_channel.py:572-607` has a single `ImessageChannelWorker` thread.
- `tools/launcher/imessage_channel.py:586-592` runs `handle_inbound_message(row)` and then `poll_outbound_once(wait_ms=reply_wait_ms)` in the same loop.
- `tools/launcher/imessage_channel.py:431-465` loads state before calling `api.read_events(...)`, so a long-poll wait currently sits inside the worker's only path.
- Existing `tests/test_imessage_channel.py` covers state isolation, actor selection, outbound projection, failed `imsg.send`, worker stop, and residue, but it does not prove nonblocking inbound handling or repeated outbound polling without inbound messages.

## Target Behavior

Worker lifecycle:

- `ImessageChannelWorker.start()` starts one inbound thread and one outbound thread.
- `run_forever()` becomes the inbound loop for compatibility with direct callers.
- Add `run_outbound_forever()` for the outbound loop.
- Both loops share one stop event.
- `stop()` sets the stop event, calls `imsg.stop()`, and joins all started worker threads.
- Background error capture identifies the loop that stopped.

Controller concurrency:

- Add a controller-level lock around channel state load/mutate/save.
- `handle_inbound_message()` stays the only inbound iMessage path.
- `poll_outbound_once()` stays the only outbound actor reply projection path.
- `poll_outbound_once()` must not hold the state lock while `api.read_events(... wait_ms=...)` is waiting.
- After a long-poll returns, `poll_outbound_once()` reloads state before route lookup and state mutation.

## Not Doing

- No asyncio rewrite.
- No generic worker/channel framework.
- No event bus.
- No old serial worker compatibility flag.
- No iMessage ack-after-projection changes; Phase 3 owns that.
- No direct imports from Central IM internals.

## Delete Or Replace Old Paths

- Replace the old `handle inbound -> poll outbound` worker path.
- Replace the single `_thread` lifecycle with explicit inbound/outbound thread tracking.
- Remove any behavior where inbound processing depends on a preceding or following outbound long-poll.

## Test Plan

### 1. Outbound long-poll does not block inbound `/actors`

Add `tests/test_imessage_channel.py::ImessageChannelTests.test_worker_processes_actors_while_outbound_poll_is_blocked`.

Test shape:

- Use a fake API whose `read_events(wait_ms=...)` sets `read_started` and blocks on `release_read`.
- Use a queue-backed fake `imsg.watch_messages()`.
- Start the worker.
- Wait until the outbound loop is blocked in `read_events`.
- Enqueue an inbound `/actors` row.
- Assert the actor list is sent before releasing the blocked outbound read.
- Stop the worker and release the read event in cleanup.

Expected failure before implementation:

```text
AssertionError: outbound read did not start
```

because the current worker only polls outbound after receiving an inbound row.

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_worker_processes_actors_while_outbound_poll_is_blocked
```

### 2. Outbound worker polls again after empty poll without new inbound

Add `tests/test_imessage_channel.py::ImessageChannelTests.test_worker_delivers_late_reply_without_new_inbound_message`.

Test shape:

- Use normal controller calls before worker start to create connection, select actor, send a normal message, and record the route.
- Configure fake API `read_events()` so the first outbound poll returns `[]`.
- After the first empty poll is observed, add an actor reply event and message to the fake API.
- Assert the worker sends the actor reply without enqueuing another inbound iMessage row.

Expected failure before implementation:

```text
AssertionError: first outbound poll did not happen
```

because the current worker has no outbound loop independent of inbound rows.

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_worker_delivers_late_reply_without_new_inbound_message
```

### 3. Stop joins both loops

Modify or add `tests/test_imessage_channel.py::ImessageChannelTests.test_worker_stop_terminates_watch_client` to prove:

- `imsg.stop()` is called.
- Blocked outbound read is released by the test cleanup.
- All started worker threads stop after `worker.stop()`.

Expected failure before implementation:

```text
AssertionError: worker still has a live outbound thread
```

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_worker_stop_terminates_watch_client
```

### 4. Web lifecycle still tolerates worker start failure

Run existing tests:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_starts_stops_and_closes_server tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_keeps_server_available_when_worker_start_fails
```

Expected:

- Existing behavior remains green.
- `serve_with_imessage_worker()` still catches `worker.start()` failure and leaves server handling available.

## Stage Acceptance

Phase 2 is complete only when:

- The new worker tests fail for the expected reasons before implementation.
- `ImessageChannelWorker` starts independent inbound and outbound loops.
- No long-poll wait holds the controller state lock.
- `stop()` stops both loops and still calls the underlying `imsg.stop()`.
- Focused tests pass:

```bash
python3 -m pytest -q tests/test_imessage_channel.py tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_starts_stops_and_closes_server tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_keeps_server_available_when_worker_start_fails
```

- Compile check passes:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py
```

## Risks

- A coarse state lock can serialize short inbound operations. This is acceptable for Phase 2 if the lock is never held during External IM long-poll.
- Multiple contacts are still polled serially by the outbound loop. This preserves existing behavior and avoids a broader queue/fanout rewrite.
- Phase 2 does not solve ack-after-iMessage-send; Phase 3 must still replace local-only outbound event consumption.

## Verification Log

RED, before implementation:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_worker_processes_actors_while_outbound_poll_is_blocked tests/test_imessage_channel.py::ImessageChannelTests::test_worker_delivers_late_reply_without_new_inbound_message tests/test_imessage_channel.py::ImessageChannelTests::test_worker_stop_terminates_watch_client
```

Result:

```text
3 failed
```

Expected failure causes observed:

- Outbound read did not start independently of inbound rows.
- First outbound poll did not happen without inbound rows.

GREEN, focused worker tests after implementation:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_worker_processes_actors_while_outbound_poll_is_blocked tests/test_imessage_channel.py::ImessageChannelTests::test_worker_delivers_late_reply_without_new_inbound_message tests/test_imessage_channel.py::ImessageChannelTests::test_worker_stop_terminates_watch_client
```

Result:

```text
3 passed in 0.08s
```

Phase focused suite:

```bash
python3 -m pytest -q tests/test_imessage_channel.py tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_starts_stops_and_closes_server tests/test_web_management.py::WebManagementUnitTests::test_serve_with_imessage_worker_keeps_server_available_when_worker_start_fails
```

Result:

```text
21 passed in 0.21s
```

Compile:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py
```

Result: passed.

Broader IM/Web focused regression:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py tests/test_imessage_channel.py
```

Result:

```text
114 passed, 74 subtests passed in 112.92s
```
