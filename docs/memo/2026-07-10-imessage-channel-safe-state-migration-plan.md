# iMessage Channel Safe State Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Web Management safely upgrade existing iMessage channel schema v4 state to schema v5 without losing the external identity binding or weakening the existing actor-selection TTL and confirmed-delivery semantics.

**Architecture:** Keep the change inside the existing iMessage channel boundary. `ImessageChannelStateStore` owns the one-way v4-to-v5 transformation and atomic persistence; `ImessageChannelController.prepare()` owns startup validation of state and `imsg`; `ImessageChannelWorker.start()` does not create threads until preparation succeeds. No migration framework, provider abstraction, IM-core change, or Web UI behavior is introduced.

**Tech Stack:** Python standard library, existing `env.repos.runtime_files` atomic JSON helper, `unittest`, existing file-backed iMessage channel state.

---

## Current Failure And Constraints

The current local runtime state at `~/.codex-buddyswitch/state/buddyswitch/local/imessage-channel/state.json` is schema v4. Commit `543fd2c` intentionally rejects v4, while all existing iMessage tests construct clean temporary state and therefore start at schema v5. Web Management starts the worker before serving HTTP, but `ImessageChannelWorker.start()` currently creates background threads without loading state; the permanent schema error is then retried in the outbound loop every 10 ms.

The repair must preserve these existing product invariants:

1. `/actors` choices become active only after the actor-list iMessage is confirmed sent.
2. Pending choices expire after `PENDING_ACTOR_CHOICE_SECONDS`.
3. Numeric actor selection becomes active only after its confirmation iMessage is confirmed sent.
4. Active actor selection expires after `ACTIVE_ACTOR_IDLE_SECONDS` and refreshes only after a successful ordinary inbound delivery.
5. Actor-to-iMessage outbound delivery remains independent of the active-actor TTL.
6. Control delivery still retries at most three times and retains its failed status and last error.

Schema v4 contains interaction fields written before the v5 confirmed-delivery contract existed. Migration therefore uses this exact policy:

- Preserve `external_session_key`.
- Preserve `external_identity_id`.
- Preserve the latest `route`.
- Preserve `seen_inbound_keys`.
- Preserve `sent_outbound_event_ids`.
- Clear `active_identity_id` and `active_identity_expires_at`.
- Clear `pending_actor_choices` and `pending_actor_choices_expires_at`.
- Do not synthesize a `control_delivery`.

After migration, the sender must use `/actors` again. This re-enters the existing v5 confirmed-delivery and TTL flow instead of trusting ambiguous v4 interaction state.

## File Responsibilities

- `tools/launcher/imessage_channel.py`: state migration, atomic save, controller preparation, and truthful worker startup.
- `tests/test_imessage_channel.py`: v4 migration regression tests, default-path startup coverage, unsupported-schema startup coverage, and all existing TTL/control-delivery behavior tests.
- `tests/test_web_management.py`: retain the existing contract that Web Management remains available when the optional iMessage worker cannot start.

## Task 1: Define The Safe v4-to-v5 State Transition

**Files:**

- Modify: `tests/test_imessage_channel.py`
- Modify: `tools/launcher/imessage_channel.py`

- [x] **Step 1: Add a failing migration regression test**

Add a test that writes a literal schema v4 file containing binding, dedupe, active actor, and pending choice fields. The expected state and on-disk file are schema v5, preserve only binding/dedupe fields, and contain an empty pending choice map with no active actor or control delivery.

```python
def test_schema_v4_state_migrates_binding_and_clears_unconfirmed_interaction(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        state_path = Path(temp_root) / "state.json"
        v4_payload = {
            "schema_version": 4,
            "contacts": {
                "sender:user-a@example.com": {
                    "external_session_key": "imsk-existing",
                    "external_identity_id": "ext-existing",
                    "route": {"chat_id": "9", "sender": "user-a@example.com"},
                    "active_identity_id": "act-market-demo",
                    "active_identity_expires_at": "2026-07-10T12:30:00Z",
                    "pending_actor_choices": {"1": "act-market-demo"},
                    "pending_actor_choices_expires_at": "2026-07-10T12:05:00Z",
                    "seen_inbound_keys": ["guid:seen"],
                    "sent_outbound_event_ids": ["imev-sent"],
                }
            },
        }
        state_path.write_text(json.dumps(v4_payload), encoding="utf-8")
        store = imessage_channel.ImessageChannelStateStore(state_path)

        migrated = store.load()
        saved = json.loads(state_path.read_text(encoding="utf-8"))

    contact = migrated["contacts"]["sender:user-a@example.com"]
    self.assertEqual(migrated, saved)
    self.assertEqual(migrated["schema_version"], 5)
    self.assertEqual(contact["external_session_key"], "imsk-existing")
    self.assertEqual(contact["external_identity_id"], "ext-existing")
    self.assertEqual(contact["route"], {"chat_id": "9", "sender": "user-a@example.com"})
    self.assertEqual(contact["seen_inbound_keys"], ["guid:seen"])
    self.assertEqual(contact["sent_outbound_event_ids"], ["imev-sent"])
    self.assertEqual(contact["pending_actor_choices"], {})
    self.assertNotIn("active_identity_id", contact)
    self.assertNotIn("active_identity_expires_at", contact)
    self.assertNotIn("pending_actor_choices_expires_at", contact)
    self.assertNotIn("control_delivery", contact)
```

- [x] **Step 2: Run the migration test and verify RED**

Run:

```bash
python3 -m unittest -q tests.test_imessage_channel.ImessageChannelTests.test_schema_v4_state_migrates_binding_and_clears_unconfirmed_interaction
```

Expected: fail with `ChannelError: iMessage channel state schema is retired`.

- [x] **Step 3: Implement the single supported migration**

In `ImessageChannelStateStore.load()`:

```python
schema_version = payload.get("schema_version")
if schema_version == 4:
    state = _migrate_schema_v4_state(payload)
    self.save(state)
    return state
if schema_version != SCHEMA_VERSION:
    raise ChannelStateError("iMessage channel state schema is retired; reset the channel state file")
```

`_migrate_schema_v4_state()` must explicitly allowlist the five preserved fields and normalize them through the existing contact normalizer. It must not copy active actor, pending choice, or control-delivery fields.

- [x] **Step 4: Use atomic JSON persistence**

Replace direct `Path.write_text()` persistence with:

```python
runtime_files.write_json_object(self.path, payload)
```

Keep the existing best-effort `chmod(0o600)` behavior and wrap persistence failures in `ChannelStateError`.

- [x] **Step 5: Run the focused migration test and verify GREEN**

Run the Step 2 command again.

Expected: one passing test.

## Task 2: Make Worker Startup Truthful

**Files:**

- Modify: `tests/test_imessage_channel.py`
- Modify: `tools/launcher/imessage_channel.py`

- [x] **Step 1: Add a failing unsupported-schema startup test**

Write schema v3 state, construct a real controller with temporary state and `_QueueImsg`, and assert that `worker.start()` raises before any worker thread or iMessage watch starts.

```python
with self.assertRaisesRegex(imessage_channel.ChannelStateError, "schema is retired"):
    worker.start()
self.assertEqual(worker._threads, [])
self.assertFalse(imsg.watch_started.is_set())
```

- [x] **Step 2: Add a failing `imsg status` startup test**

Use a fake client whose `status()` raises `ChannelError("imsg unavailable")`. Assert that `worker.start()` raises synchronously and leaves `_threads` empty.

- [x] **Step 3: Run both startup tests and verify RED**

Run:

```bash
python3 -m unittest -q \
  tests.test_imessage_channel.ImessageChannelTests.test_worker_rejects_unsupported_state_before_starting_threads \
  tests.test_imessage_channel.ImessageChannelTests.test_worker_rejects_unavailable_imsg_before_starting_threads
```

Expected: both tests fail because the current `start()` returns after creating background threads.

- [x] **Step 4: Add controller preparation and call it before thread creation**

Add:

```python
def prepare(self) -> None:
    with self._state_lock:
        self.state_store.load()
    self.imsg.status()
```

Call `self.controller.prepare()` in `ImessageChannelWorker.start()` before clearing the stop event or assigning `_threads`. Remove the duplicate `imsg.status()` call from `run_forever()`.

- [x] **Step 5: Run both startup tests and verify GREEN**

Run the Step 3 command again.

Expected: two passing tests and no background error output.

## Task 3: Prove The Default Runtime Path And Existing Features

**Files:**

- Modify: `tests/test_imessage_channel.py`
- Verify: `tests/test_web_management.py`

- [x] **Step 1: Add a default-path worker migration test**

Patch `runtime_files.LOCAL_ROOT` to a temporary root, write v4 state under `imessage-channel/state.json`, construct `ChannelConfig` without `state_path`, start a worker with fake API/imsg, and assert the on-disk schema is v5 with the preserved binding and cleared interaction state.

- [x] **Step 2: Verify the default-path test passes after Tasks 1 and 2**

Run:

```bash
python3 -m unittest -q tests.test_imessage_channel.ImessageChannelTests.test_worker_start_migrates_schema_v4_from_default_runtime_path
```

Expected: one passing test.

- [x] **Step 3: Run the complete iMessage channel suite**

Run:

```bash
python3 -m unittest -q tests.test_imessage_channel
```

Expected: all tests pass, including existing TTL, confirmed-delivery, retry, dedupe, route, worker concurrency, and send-status tests.

- [x] **Step 4: Run the Web Management worker lifecycle tests**

Run:

```bash
python3 -m unittest -q \
  tests.test_web_management.WebManagementUnitTests.test_serve_with_imessage_worker_starts_stops_and_closes_server \
  tests.test_web_management.WebManagementUnitTests.test_serve_with_imessage_worker_keeps_server_available_when_worker_start_fails
```

Expected: both tests pass and Web remains available when startup preparation fails.

## Task 4: End-to-End Verification And Acceptance

Before final acceptance, independent code review added two required lifecycle checks:

- [x] **Reviewer Follow-Up 1: Bound synchronous `imsg status` preparation**

Add a failing `CommandImsgClient.status()` test whose injected subprocess runner raises `subprocess.TimeoutExpired`. Require `status()` to pass a five-second timeout and translate expiry into `ChannelError("iMessage status check timed out")`. This keeps worker preparation synchronous and truthful without allowing the optional channel to block Web startup indefinitely.

- [x] **Reviewer Follow-Up 2: Protect atomic persistence with tests**

Patch `runtime_files.write_json_object` with `wraps=` and prove `ImessageChannelStateStore.save()` calls it. Patch it again with `side_effect=OSError("disk full")` and assert `ChannelStateError("failed to save iMessage channel state")`. These tests protect both use of the atomic writer and the state-specific error boundary.

**Files:**

- Update: `docs/memo/2026-07-10-imessage-channel-safe-state-migration-plan.md`
- Verify: `tools/launcher/imessage_channel.py`
- Verify: `tools/launcher/web_management.py`
- Verify: `tests/test_imessage_channel.py`
- Verify: `tests/test_web_management.py`

- [x] **Step 1: Run the broader Python verification**

Run:

```bash
python3 -m unittest -q tests.test_imessage_channel tests.test_web_management
```

Expected: all iMessage and Web Management tests pass.

- [x] **Step 2: Verify a copy of the real v4 state**

Copy the real state into a temporary directory, load that copy through `ImessageChannelStateStore`, and inspect only non-secret metadata. Expected:

```text
schema_version=5
contact_count unchanged
binding fields preserved
active/pending interaction fields absent or empty
```

Do not modify the real runtime state during verification.

- [x] **Step 3: Re-run focused TTL and confirmed-delivery tests**

Run the existing tests for actor-list activation, numeric-selection activation, expired active actor, expired pending choice, ordinary-message TTL refresh, and outbound delivery independent of active TTL.

Expected: all pass unchanged.

- [x] **Step 4: Inspect the final diff and state ownership boundaries**

Run:

```bash
git diff --check
git diff --stat
git status --short --branch
rg -n "pending_actor_choices|active_identity_expires_at|control_delivery" \
  tools/launcher/web_management.py tools/launcher/im_http_router.py \
  scripts/env/services scripts/env/repos scripts/env/tool_runtime
```

Expected: no whitespace errors; changes are limited to the plan, iMessage implementation/tests, and any directly required Web worker lifecycle test; no iMessage selection semantics leak into Web or IM core.

- [x] **Step 5: Update this plan's checkboxes and perform requirement-by-requirement acceptance**

Completion requires evidence that:

1. Realistic v4 state safely becomes v5.
2. External identity/session binding, route, and dedupe fields survive.
3. Ambiguous v4 active/pending interaction state is not trusted.
4. Existing TTL and confirmed-delivery features remain unchanged.
5. Unsupported state and unavailable `imsg` fail before threads start.
6. Web Management can remain available when the optional worker fails startup.
7. Complete iMessage and Web Management suites pass.
8. The real runtime state was not directly modified by verification.

### Acceptance Evidence

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q tests.test_imessage_channel tests.test_web_management`: 126 tests passed.
- Six focused actor-list, actor-selection, expiry, TTL-refresh, and outbound-independence tests passed unchanged.
- A copy of the real schema v4 state migrated to schema v5 with the contact count and stable binding fingerprints preserved.
- The migrated copy cleared active actor, active expiry, pending choice expiry, and control delivery while keeping `pending_actor_choices` empty.
- The real runtime state hash was unchanged before and after copy-based verification.
- `python3 -m py_compile`, `git diff --check`, and the iMessage semantic boundary scan passed.
- Independent code review found no remaining issues after adding the bounded `imsg status` check and atomic persistence tests.

## Explicit Non-Goals

- No generic schema migration registry.
- No migration for schema v3 or older.
- No schema v6 redesign.
- No IM core, router, actor tool, Task Sys, or Web UI semantic change.
- No change to TTL durations.
- No preservation of v4 active actor or pending choice state.
- No direct modification of the user's real runtime state during tests.
- No remote push.
