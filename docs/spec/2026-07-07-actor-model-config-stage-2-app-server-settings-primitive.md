# Actor Model Config Stage 2 Plan: App-Server Settings Primitive

Date: 2026-07-07

## Stage Target

Add the raw app-server primitive needed by the later parent actor boundary:

```text
thread/settings/update -> wait for matching thread/settings/updated notification
```

This stage covers memo Task 3 only. It must not read `model-config.json` and must not decide when parent policy applies.

## Current Code Facts

- `tools/launcher/app_server.py::AppServerClient.request(...)` currently discards notifications while waiting for a JSON-RPC response.
- Parent hot-load requires preserving the `thread/settings/updated` notification even if it arrives before the JSON-RPC response.
- `tools/launcher/app_server.py` already defines `AppServerProtocolError`, `_optional_non_empty_text(...)`, `DEFAULT_RPC_TIMEOUT_SECONDS`, and the websocket JSON-RPC loop.
- `tests/test_app_server_client.py` already has `FakeUnixWebSocketServer`, which can send responses and notifications in controlled order.

## Files

Modify:

- `tools/launcher/app_server.py`
- `tests/test_app_server_client.py`
- `docs/spec/2026-07-07-actor-model-config-stage-2-app-server-settings-primitive.md`

Do not modify in this stage:

- `tools/launcher/parent_thread_submit.py`
- `tools/launcher/actor_side_thread.py`
- `tools/launcher/submit_turn.py`
- `tools/launcher/side_thread_lifecycle.py`
- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/daemon_core.py`
- `buddyswitch-codex`

## Module Boundary

`app_server.py` owns:

- JSON-RPC request framing.
- Waiting for a response and selected notification on the same socket.
- Building `thread/settings/update` params.

`app_server.py` does not own:

- Reading or interpreting `model-config.json`.
- Deciding whether a parent submit should update settings.
- Side-thread model policy.

## Development Steps

### Step 1: Write Failing App-Server Tests

Add tests to `tests/test_app_server_client.py` for:

- `build_thread_settings_update_params("thread-main", model="gpt-5.4", effort="high")` returns:

```python
{
    "threadId": "thread-main",
    "model": "gpt-5.4",
    "effort": "high",
}
```

- `build_thread_settings_update_params(...)` omits absent optional fields.
- `build_thread_settings_update_params("thread-main")` raises `AppServerProtocolError`.
- `thread_settings_update(...)` sends method `thread/settings/update`.
- It sends params `{"threadId": "thread-main", "model": "gpt-5.4", "effort": "high"}`.
- It returns the matching `thread/settings/updated` notification payload when the notification arrives before the JSON-RPC response.
- It returns the matching `thread/settings/updated` notification payload when the notification arrives after the JSON-RPC response.
- It ignores unrelated notifications.

Run:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Expected before implementation:

```text
failed
```

### Step 2: Implement Request-With-Notification

Add `AppServerClient.request_with_notification(...)`:

```python
def request_with_notification(
    self,
    method: str,
    params: dict[str, object] | None,
    *,
    notification_method: str,
    notification_thread_id: str | None = None,
) -> dict[str, object]:
    ...
```

Required behavior:

- Send one JSON-RPC request.
- Read messages until both the matching response and matching notification have been observed.
- Store a matching notification that arrives before the response.
- Store a matching response that arrives before the notification.
- Ignore other notifications and unrelated response ids.
- Raise `AppServerRequestError` for JSON-RPC errors.
- Raise `AppServerProtocolError` for invalid result or notification shapes.
- Return the matching notification `params` payload.

### Step 3: Implement Thread Settings Helpers

Add:

```python
def build_thread_settings_update_params(
    thread_id: str,
    *,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, object]: ...

def thread_settings_update(
    socket_path: Path,
    thread_id: str,
    *,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]: ...
```

Required behavior:

- `thread_id` must be non-empty.
- `model` and `effort`, when present, must be non-empty strings.
- Both absent raises `AppServerProtocolError`.
- Absent fields are omitted, not sent as `None`.
- `thread_settings_update(...)` opens `AppServerClient` with `DEFAULT_RPC_TIMEOUT_SECONDS`.
- It calls `request_with_notification(...)` with method `thread/settings/update`, notification method `thread/settings/updated`, and `notification_thread_id=thread_id`.

### Step 4: Run Stage Verification

Run:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Expected:

```text
passed
```

### Step 5: Run Boundary Scan

Run:

```bash
rg -n "model-config.json" tools/launcher/app_server.py
```

Expected:

```text
no output
```

## Stage Acceptance

Stage 2 is accepted only when:

- The app-server tests prove settings params and before/after notification ordering.
- `thread_settings_update(...)` returns notification params.
- `build_thread_settings_update_params(...)` refuses no-op updates.
- `app_server.py` still has no `model-config.json` reference.
- This stage doc is updated with exact test and scan results.

## Completion Notes

- Added `AppServerClient.request_with_notification(...)` to preserve a matching notification while also waiting for the JSON-RPC response.
- Added `build_thread_settings_update_params(...)` with no-op rejection and absent-field omission.
- Added `thread_settings_update(...)` as the public raw app-server primitive.
- Added tests covering before-response and after-response notification ordering.

## Test Results

Red check:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Result:

```text
3 failed, 27 deselected
AttributeError: module 'buddyswitch_launcher_app_server' has no attribute 'build_thread_settings_update_params'
```

Green check:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Result:

```text
3 passed, 27 deselected in 0.02s
```

## Residue Scan Results

Command:

```bash
rg -n "model-config.json" tools/launcher/app_server.py
```

Result:

```text
no output
```

## Remaining Risk

Parent submit behavior is intentionally not implemented in this stage. Stage 3 will own when to call this primitive.
