# iMessage Channel Actor Connection TTL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the iMessage channel actor selection UX so a selected actor is a time-bounded channel-local connection instead of a permanent default target.

**Architecture:** Keep the capability inside `tools/launcher/imessage_channel.py`. iMessage channel owns `/actors`, numeric actor selection, selected actor TTL, pending choice TTL, and iMessage route state. IM API and IM core remain identity-based messaging projections and do not gain selected-actor semantics.

**Tech Stack:** Python stdlib, file-backed iMessage channel state JSON, `/api/im/*` HTTP projection, `unittest`, `pytest`.

---

## 1. Task Restatement

The current iMessage channel stores `active_identity_id` indefinitely after a user sends `/actors` and replies with a numeric actor choice. That means an iMessage sender can stop for an hour and then send a new message that is still routed to the old selected actor.

The target behavior is:

```text
iMessage user sends /actors
-> channel lists reachable actors
-> user replies with a valid number during a short choice window
-> channel creates a selected-actor connection with an idle TTL
-> ordinary iMessage text routes to that actor while the TTL is valid
-> each successful ordinary message refreshes the idle TTL
-> after TTL expiry, ordinary text is not written to IM and the user is prompted to choose again
```

The selected-actor connection is channel-local UX state. It is not an IM conversation, not an external session lifecycle, not actor reachability state, and not identity profile state.

## 2. Bitter Principles Applied

Read and apply:

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`

Implications for this task:

- Fix the owning layer. The owning layer is iMessage channel UX state, not IM core.
- Keep the shared product boundary stable. Do not add default-target semantics to `/api/im/messages`.
- Prove behavior and live surface. Tests must cover TTL behavior and source checks must prevent the old indefinite-selection path from being reintroduced.
- Rebuild forward. Do not keep schema-v3 selected actor state alive through compatibility code.
- Avoid guarded residue. Do not add runtime branches that remember retired v3 shape to preserve old permanent `active_identity_id` behavior.

## 3. Current Code Review

### iMessage Channel State

File: `tools/launcher/imessage_channel.py`

Current facts:

- `SCHEMA_VERSION = 3`.
- `ImessageChannelStateStore.load()` rejects non-current schema versions.
- `_default_contact()` contains:
  - `pending_actor_choices`
  - `seen_inbound_keys`
  - `sent_outbound_event_ids`
- `_normalize_contact()` preserves:
  - `external_session_key`
  - `external_identity_id`
  - `route`
  - `active_identity_id`
  - `pending_actor_choices`
  - `seen_inbound_keys`
  - `sent_outbound_event_ids`
- There is no `active_identity_expires_at`.
- There is no `pending_actor_choices_expires_at`.
- There is no time parsing or TTL decision inside the iMessage channel.

### Inbound Flow

File: `tools/launcher/imessage_channel.py`

Current path:

```text
handle_inbound_message(row)
-> load state
-> resolve sender and route
-> bind external session / external identity
-> if content == "/actors": _handle_actors(state, contact, external_session_key, route, now=now)
-> if numeric and pending_actor_choices exists: _handle_numeric_choice(state, contact, content, route, now=now)
-> otherwise: _handle_ordinary_message(state, contact, external_session_key, row, sender=sender, content=content, route=route, now=now)
```

Current behavior:

- `/actors` writes `contact["pending_actor_choices"] = choices`.
- Numeric selection writes `contact["active_identity_id"] = selected`.
- Successful selection does not clear `pending_actor_choices`.
- Ordinary message reads `_active_identity_id(contact)` and sends to that actor.
- No expiry check exists.

### Outbound Flow

File: `tools/launcher/imessage_channel.py`

Current path:

```text
poll_outbound_once(wait_ms=wait_ms, limit=limit)
-> read events by external_session_key
-> fetch message
-> send iMessage through contact.route
-> ack after successful iMessage send
```

This flow must remain independent from selected actor TTL. Actor-to-external delivery is driven by external session and contact route, not by the inbound selected actor. Expiring the selected actor must not delete `external_session_key`, `external_identity_id`, `route`, or `sent_outbound_event_ids`.

### Tests

File: `tests/test_imessage_channel.py`

Current coverage proves:

- first sender creates one external session and reuses it;
- `/actors` lists reachable actors and stores pending choices;
- numeric selection stores `active_identity_id`;
- ordinary message without active actor prompts and does not call API send;
- ordinary message with active actor posts to `/api/im/messages`;
- outbound actor reply and proactive message use contact route, not `reply_to`;
- residue tests keep iMessage channel semantics out of web/router/core.

Missing coverage:

- selected actor gets an expiry timestamp;
- pending choices get an expiry timestamp;
- pending choices are cleared after successful selection;
- expired pending choices cannot be used by later numeric input;
- expired active actor blocks ordinary inbound send and clears active state;
- successful ordinary inbound send refreshes selected actor idle TTL;
- source no longer permits direct selected-actor reads or writes that bypass TTL helpers.

## 4. System Architecture Boundary

### iMessage Channel Owns

- iMessage sender identity normalization, for example `sender:hblouis@126.com`.
- iMessage route to real external address/chat.
- External session key and external identity returned by `/api/im/external-sessions`.
- `/actors` channel command.
- Numeric choice interpretation.
- Selected actor connection TTL.
- Pending actor choice TTL.
- User-facing prompt when no selected actor connection is active.

### IM API Owns

- `/api/im/external-sessions`
- `/api/im/actors`
- `/api/im/messages`
- `/api/im/events`
- `/api/im/events/ack`
- `/api/im/messages/{message_id}`
- `/api/im/conversations/direct`

It does not own iMessage `/actors` command state or the selected actor TTL.

### IM Core Owns

- identity target validation;
- actor/external reach and send eligibility;
- direct conversation creation/reuse;
- message persistence;
- message state;
- events.

It does not know whether the iMessage channel currently has an active selected actor.

### Explicit Non-Boundaries

- Do not put selected actor TTL in identity profiles.
- Do not put selected actor TTL in external session records.
- Do not put selected actor TTL in IM conversation records.
- Do not add default-target behavior to `/api/im/messages`.
- Do not change actor tool `message.send(target_identity_id=<identity-id>, content=<text>) or message.send(reply_to=<message-id>, content=<text>)`.
- Do not change Web UI target selection behavior.

## 5. Target State Schema

Move iMessage channel state from schema v3 to schema v4.

Current v3 shape allows permanent `active_identity_id`. That is the retired shape for this task. The implementation must not silently accept v3 state and interpret a missing expiry as permanent.

Target contact shape:

```json
{
  "external_session_key": "imsk-example",
  "external_identity_id": "ext-example",
  "route": {
    "chat_guid": "iMessage;-;user@example.com",
    "chat_id": "3213",
    "chat_identifier": "user@example.com",
    "sender": "user@example.com"
  },
  "active_identity_id": "act-pm-example",
  "active_identity_expires_at": "2026-07-08T12:30:00Z",
  "pending_actor_choices": {
    "1": "act-market-example",
    "2": "act-pm-example"
  },
  "pending_actor_choices_expires_at": "2026-07-08T12:05:00Z",
  "seen_inbound_keys": [
    "guid:inbound-example"
  ],
  "sent_outbound_event_ids": [
    "imev-outbound-example"
  ]
}
```

Allowed absence:

- If there is no selected actor, omit `active_identity_id` and `active_identity_expires_at`.
- If there is no pending choice window, keep `pending_actor_choices` as `{}` and omit `pending_actor_choices_expires_at`.

Required rule:

- `active_identity_id` is usable only when `active_identity_expires_at` exists and is after current time.
- `pending_actor_choices` is usable only when non-empty and `pending_actor_choices_expires_at` exists and is after current time.
- Missing expiry never means permanent.

## 6. Time Semantics

Use channel-local idle TTL:

- `ACTIVE_ACTOR_IDLE_SECONDS = 30 * 60`
- `PENDING_ACTOR_CHOICE_SECONDS = 5 * 60`

Time format:

- Store UTC ISO timestamps ending in `Z`, for example `2026-07-08T12:30:00Z`.
- Parse both `Z` and offset timestamps defensively for current schema, then normalize comparisons to UTC.
- Invalid timestamp means the related state is unusable and should be cleared by the helper that reads it.

Clock:

- Add one private local clock seam to `ImessageChannelController`, defaulting to a module helper that returns current UTC datetime.
- This is not a service abstraction. It exists only to make TTL tests deterministic without sleeps.
- Do not expose the clock through CLI, HTTP, config files, or IM API.

## 7. Target Inbound State Machine

### `/actors`

Input:

```text
iMessage content == "/actors"
```

Action:

- call `/api/im/actors` through `BuddySwitchImApi.list_actors(external_session_key=external_session_key)`;
- filter reachable actors with `_actor_is_reachable(actor)`;
- write `pending_actor_choices`;
- write `pending_actor_choices_expires_at = now + PENDING_ACTOR_CHOICE_SECONDS`;
- leave current active selected actor unchanged;
- save state;
- send actor list through iMessage route.

### Numeric Choice

Input:

```text
content is numeric and pending choices are still valid
```

Action:

- resolve selected actor from pending choices;
- if valid:
  - write `active_identity_id`;
  - write `active_identity_expires_at = now + ACTIVE_ACTOR_IDLE_SECONDS`;
  - clear `pending_actor_choices`;
  - remove `pending_actor_choices_expires_at`;
  - save state;
  - send short confirmation containing selected actor id.
- if invalid and there is no valid active actor:
  - clear expired or invalid pending state;
  - save state;
  - prompt `Send /actors to choose an actor.`
- if invalid and there is a valid active actor:
  - treat as ignored invalid choice as current behavior does, or route ordinary numeric content only when the pending window has expired.

Implementation detail:

- The decision whether a numeric message is a selection command must use a helper that checks pending TTL.
- Do not use `contact.get("pending_actor_choices")` directly as the selection gate.

### Ordinary Message

Input:

```text
content is not /actors and is not a valid in-window numeric selection
```

Action:

- read selected actor through a TTL-aware helper;
- if no selected actor or selected actor expired:
  - clear expired active state;
  - save state;
  - do not call `/api/im/messages`;
  - send `Send /actors to choose an actor.`
- if selected actor is valid:
  - perform existing inbound dedupe check;
  - call `/api/im/messages` with `target_identity_id=active_identity_id`;
  - after successful API send and valid message id:
    - record inbound key;
    - refresh `active_identity_expires_at = now + ACTIVE_ACTOR_IDLE_SECONDS`;
    - save state;
  - return delivered status.

### Outbound Actor Message

Input:

```text
actor message to external identity creates an event visible to external identity
```

Action:

- leave existing `poll_outbound_once(wait_ms=wait_ms, limit=limit)` route model unchanged;
- poll by `external_session_key`;
- fetch message;
- send through `contact.route`;
- ack after successful iMessage send.

Selected actor TTL must not gate outbound delivery. A late actor reply can still be delivered to the iMessage sender through the external session route.

## 8. Files To Modify

### Modify: `tools/launcher/imessage_channel.py`

Responsibilities:

- bump state schema to v4;
- define active/pending TTL constants;
- add local UTC parse/format helpers;
- add controller-local deterministic clock seam;
- normalize current v4 fields;
- replace direct selected actor and pending choice access with TTL-aware helpers;
- refresh active actor TTL after successful ordinary inbound message;
- clear pending choices after successful selection;
- keep outbound route polling independent from selected actor TTL.

### Modify: `tests/test_imessage_channel.py`

Responsibilities:

- update default schema version assertion to v4;
- add deterministic controller clock helper;
- update existing actor selection tests for expiry fields and pending clear;
- add active actor expiry tests;
- add pending choices expiry tests;
- add idle TTL refresh tests;
- add a regression proving outbound route delivery does not depend on selected actor TTL;
- add residue checks for no direct old permanent selected-actor path.

### Do Not Modify

- `tools/launcher/im_http_router.py`
- `tools/launcher/external_im_session.py`
- `scripts/env/services/messages.py`
- `scripts/env/repos/messages.py`
- `scripts/env/tool_runtime/im_client.py`
- Web UI JavaScript or CSS
- actor tool schemas
- daemon reachability code

If a test appears to require modifying one of these files, stop and re-check the boundary. The expected owner for this task is still iMessage channel.

## 9. Implementation Phases

### Phase 1: Tests Define The New State Semantics

Goal: make tests teach time-bounded selected actor behavior before implementation.

- [ ] Update `test_default_state_path_uses_imessage_channel_schema_v3` to schema v4 and rename it to schema v4.
- [ ] Add a deterministic test controller helper that passes fixed UTC time into the controller.
- [ ] Update `/actors` list test to assert `pending_actor_choices_expires_at` exists and is `now + 5 minutes`.
- [ ] Update numeric selection test to assert:
  - `active_identity_id` is set;
  - `active_identity_expires_at` is `now + 30 minutes`;
  - `pending_actor_choices` is `{}`;
  - `pending_actor_choices_expires_at` is absent.
- [ ] Add `test_expired_active_actor_prompts_without_posting_message`.
- [ ] Add `test_expired_pending_choice_is_not_used_for_numeric_selection`.
- [ ] Add `test_successful_ordinary_message_refreshes_active_actor_idle_ttl`.
- [ ] Add `test_outbound_delivery_ignores_active_actor_ttl`.
- [ ] Add residue test assertions that source has no direct permanent selected actor access.

Focused red command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_imessage_channel.py -q
```

Expected before implementation:

```text
fails on schema version, missing expiry fields, stale direct access, and TTL behavior
```

### Phase 2: State Schema V4 And Time Helpers

Goal: create current state shape without preserving v3 permanent selection.

- [ ] In `tools/launcher/imessage_channel.py`, set `SCHEMA_VERSION = 4`.
- [ ] Import `datetime`, `timedelta`, and `timezone`.
- [ ] Add constants:

```python
ACTIVE_ACTOR_IDLE_SECONDS = 30 * 60
PENDING_ACTOR_CHOICE_SECONDS = 5 * 60
```

- [ ] Add private helpers:

```python
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
```

- [ ] Add a private constructor parameter on `ImessageChannelController`:

```python
now_fn: Callable[[], datetime] | None = None
```

- [ ] Store:

```python
self._now_fn = now_fn or _utc_now
```

- [ ] Use only `self._now_fn()` inside controller TTL decisions.

Acceptance:

- schema v3 state is rejected by existing version check;
- schema v4 empty state loads;
- no migration branch names v3 internals beyond the generic schema-version error.

### Phase 3: TTL-Aware Contact Helpers

Goal: put all selected actor and pending choice access behind local helpers.

- [ ] Replace `_active_identity_id(contact)` with a TTL-aware helper that accepts `now`.
- [ ] Add helper to set active selected actor:

```python
def _set_active_identity(contact: dict[str, Any], identity_id: str, *, now: datetime) -> None:
    contact["active_identity_id"] = identity_id
    contact["active_identity_expires_at"] = _format_utc(now + timedelta(seconds=ACTIVE_ACTOR_IDLE_SECONDS))
```

- [ ] Add helper to clear active selected actor:

```python
def _clear_active_identity(contact: dict[str, Any]) -> None:
    contact.pop("active_identity_id", None)
    contact.pop("active_identity_expires_at", None)
```

- [ ] Add helper to read active selected actor:

```python
def _active_identity_id(contact: dict[str, Any], *, now: datetime) -> str:
    value = contact.get("active_identity_id")
    expires_at = _parse_utc(contact.get("active_identity_expires_at"))
    if not isinstance(value, str) or not value.strip() or expires_at is None or expires_at <= now.astimezone(timezone.utc):
        _clear_active_identity(contact)
        return ""
    return value.strip()
```

- [ ] Add helpers to set, clear, and read pending choices:

```python
def _set_pending_choices(contact: dict[str, Any], choices: dict[str, str], *, now: datetime) -> None:
    contact["pending_actor_choices"] = dict(choices)
    contact["pending_actor_choices_expires_at"] = _format_utc(now + timedelta(seconds=PENDING_ACTOR_CHOICE_SECONDS))


def _clear_pending_choices(contact: dict[str, Any]) -> None:
    contact["pending_actor_choices"] = {}
    contact.pop("pending_actor_choices_expires_at", None)


def _pending_choices(contact: dict[str, Any], *, now: datetime) -> dict[str, str]:
    choices = _string_dict(contact.get("pending_actor_choices"))
    expires_at = _parse_utc(contact.get("pending_actor_choices_expires_at"))
    if not choices or expires_at is None or expires_at <= now.astimezone(timezone.utc):
        _clear_pending_choices(contact)
        return {}
    contact["pending_actor_choices"] = choices
    return choices
```

- [ ] Update `_normalize_contact(payload)` to allowlist:
  - `active_identity_expires_at`
  - `pending_actor_choices_expires_at`
- [ ] Preserve only parseable expiry values.
- [ ] Do not compare expiry in `_normalize_contact(payload)`; expiry is evaluated when the contact is used.

Acceptance:

- source has one clear path to set active actor with expiry;
- source has one clear path to read active actor with expiry;
- source has one clear path to set/read pending choices with expiry.

### Phase 4: Rebuild Inbound Selection And Message Flow

Goal: make user-visible iMessage inbound behavior time-bounded.

- [ ] In `handle_inbound_message(row)`, compute:

```python
now = self._now_fn()
```

inside the state lock after contact is loaded.

- [ ] Change numeric selection gate from:

```python
if _is_numeric_choice(content) and contact.get("pending_actor_choices"):
```

to a TTL-aware decision using `_pending_choices(contact, now=now)`.

- [ ] Change `_handle_actors(state, contact, external_session_key, route, now=now)` to accept `now`.
- [ ] In `_handle_actors(state, contact, external_session_key, route, now=now)`, replace direct pending assignment with `_set_pending_choices(contact, choices, now=now)`.
- [ ] Change `_handle_numeric_choice(state, contact, content, route, now=now)` to accept `now`.
- [ ] In `_handle_numeric_choice(state, contact, content, route, now=now)`, read choices through `_pending_choices(contact, now=now)`.
- [ ] On valid choice:
  - call `_set_active_identity(contact, selected, now=now)`;
  - call `_clear_pending_choices(contact)`;
  - save state.
- [ ] When checking whether there is an active actor after invalid selection, use `_active_identity_id(contact, now=now)`.
- [ ] Change `_handle_ordinary_message(state, contact, external_session_key, row, sender=sender, content=content, route=route, now=now)` to accept `now`.
- [ ] In `_handle_ordinary_message(state, contact, external_session_key, row, sender=sender, content=content, route=route, now=now)`, read active actor with `_active_identity_id(contact, now=now)`.
- [ ] If no active actor after TTL check:
  - save state so expired fields are cleared;
  - send `DEFAULT_NO_ACTOR_PROMPT`;
  - return `needs_actor`;
  - do not call API send.
- [ ] After successful API send and message id validation:
  - record inbound key;
  - refresh active TTL by calling `_set_active_identity(contact, active_identity_id, now=now)`;
  - save state.

Acceptance:

- A selected actor is never used without a non-expired `active_identity_expires_at`.
- A pending numeric choice is never used without a non-expired `pending_actor_choices_expires_at`.
- Ordinary successful user message extends the selected actor idle window.
- Expired state is cleared opportunistically when a message arrives; no background timer is added.

### Phase 5: Residue And Boundary Tests

Goal: prevent the old permanent-selection semantics from staying live.

- [ ] In `tests/test_imessage_channel.py`, extend residue tests so `tools/launcher/imessage_channel.py` does not contain:

```text
contact["active_identity_id"] = selected
contact.get("pending_actor_choices")
def _active_identity_id(contact: dict[str, Any]) -> str
```

- [ ] Add positive source assertions that current helpers exist:

```text
active_identity_expires_at
pending_actor_choices_expires_at
ACTIVE_ACTOR_IDLE_SECONDS
PENDING_ACTOR_CHOICE_SECONDS
```

- [ ] Keep existing boundary test that rejects iMessage channel semantics in:
  - `tools/launcher/web_management.py`
  - `tools/launcher/im_http_router.py`
  - `scripts/env/services`
  - `scripts/env/repos`

Acceptance:

- Old direct permanent selected actor path is not taught by live source.
- iMessage channel TTL terms do not leak into IM API/core.

## 10. Test Plan

### Focused Unit Behavior

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_imessage_channel.py -q
```

Expected:

```text
all iMessage channel behavior and residue tests pass
```

Required behavior coverage:

- default state uses schema v4;
- `/actors` creates pending choices with 5-minute expiry;
- numeric selection creates active actor with 30-minute expiry;
- numeric selection clears pending choices;
- numeric selection does not call `/api/im/messages`;
- ordinary message without active actor prompts and does not send;
- ordinary message with active actor sends to selected actor;
- ordinary successful send refreshes idle TTL;
- expired active actor prompts and does not send;
- expired active actor clears active fields;
- expired pending choices are not usable;
- outbound actor delivery still uses contact route and ignores active actor TTL.

### IM API Boundary Regression

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_http_router.py tests/test_external_im_session.py tests/test_im_web_management_projection.py -q
```

Expected:

```text
IM API and external session projection behavior remains unchanged
```

### Repository Consistency

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

```text
repo consistency checks pass
```

### Source Scans

Run:

```bash
rg -n "SCHEMA_VERSION = 3|contact\\[\"active_identity_id\"\\] = selected|contact\\.get\\(\"pending_actor_choices\"\\)|def _active_identity_id\\(contact: dict\\[str, Any\\]\\) -> str" tools/launcher/imessage_channel.py tests/test_imessage_channel.py
```

Expected:

```text
no matches
```

Run:

```bash
rg -n "active_identity_expires_at|pending_actor_choices_expires_at|ACTIVE_ACTOR_IDLE_SECONDS|PENDING_ACTOR_CHOICE_SECONDS" tools/launcher/imessage_channel.py tests/test_imessage_channel.py
```

Expected:

```text
matches in iMessage channel implementation and tests only
```

Run:

```bash
rg -n "active_identity_expires_at|pending_actor_choices_expires_at|ACTIVE_ACTOR_IDLE_SECONDS|PENDING_ACTOR_CHOICE_SECONDS" tools/launcher/im_http_router.py tools/launcher/external_im_session.py scripts/env/services scripts/env/repos scripts/env/tool_runtime
```

Expected:

```text
no matches
```

## 11. Acceptance Contract

User-visible contract:

```text
iMessage user chooses an actor through /actors
-> sends ordinary iMessage within 30 idle minutes
-> BuddySwitch posts the message to the selected actor through /api/im/messages
-> user stops sending for more than 30 idle minutes
-> next ordinary iMessage is not posted to the old actor
-> channel replies with "Send /actors to choose an actor."
```

Pending choice contract:

```text
iMessage user requests /actors
-> waits beyond the pending choice window
-> sends "1"
-> channel does not use the stale actor list
```

Outbound delivery contract:

```text
actor sends or replies to the external identity
-> iMessage channel polls the external session event
-> channel sends to contact.route
-> selected actor TTL does not block delivery
```

## 12. Non-Goals

- No IM core conversation change.
- No `/api/im/messages` default target.
- No actor reachability caching in iMessage channel.
- No external session lifecycle change.
- No identity profile schema change.
- No Web UI change.
- No daemon change.
- Do not modify actor tool schemas.
- No background TTL sweeper.
- No schema v3 migration.
- No compatibility fallback for permanent `active_identity_id`.

## 13. Implementation Risks And Controls

### Risk: TTL Accidentally Blocks Actor Replies

Control:

- Keep `poll_outbound_once(wait_ms=wait_ms, limit=limit)` independent from `_active_identity_id(contact, now=now)`.
- Add `test_outbound_delivery_ignores_active_actor_ttl`.

### Risk: Numeric Text Is Misclassified

Control:

- Numeric text is a selection only when `_pending_choices(contact, now=now)` returns non-empty choices.
- Expired pending choices are cleared before classification completes.

### Risk: State v3 Silently Keeps Permanent Selection

Control:

- Bump `SCHEMA_VERSION` to 4.
- Keep existing version rejection.
- Do not write migration code.
- Add source scan for `SCHEMA_VERSION = 3`.

### Risk: TTL Leaks Into IM Core

Control:

- Keep all changes in iMessage channel and tests.
- Run boundary scan over `im_http_router.py`, `external_im_session.py`, `scripts/env/services`, `scripts/env/repos`, and `scripts/env/tool_runtime`.

### Risk: Tests Need Sleeping

Control:

- Use the controller-local deterministic `now_fn`.
- Do not call `time.sleep()` for TTL behavior tests.

## 14. Done Definition

This task is complete only when:

- iMessage channel state schema is v4;
- selected actor cannot be used without a valid expiry timestamp;
- pending actor choices cannot be used without a valid expiry timestamp;
- successful ordinary inbound messages refresh selected actor idle TTL;
- expired active actor state is cleared and prompts without posting an IM message;
- expired pending choice state is cleared and cannot select an actor;
- outbound actor-to-external iMessage delivery remains route-based and not selected-actor-gated;
- no selected actor TTL terms leak into IM API/core;
- focused iMessage tests pass;
- IM API boundary regression tests pass;
- repo consistency test passes;
- scoped source scans produce expected results.
