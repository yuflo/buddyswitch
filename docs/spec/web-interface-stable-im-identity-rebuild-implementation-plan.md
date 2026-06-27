# Web Interface Stable IM Identity Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Web Management IM so one shared runtime has exactly one stable server-owned WebUI external participant, with no Browser token registration and no WebUI `/api/im/*` compatibility path.

**Architecture:** Web-interface owns a small local IM identity provider and exposes first-party `/api/web/im/*` routes to Browser UI. Existing IM service/router remain the lower/external IM contract, but Web Management no longer forwards `/api/im/*` to Browser-facing callers.

**Tech Stack:** Python `http.server` Web Management service, `env.services.messages`, runtime file helpers, vanilla Browser JavaScript, Python `unittest`/`pytest`, Node `assert` tests.

---

## Confirmed Target

Web Management represents one stable external user inside one shared runtime.

- First Web Management startup registers one external participant.
- Page refresh does not register.
- Page reopen does not register.
- Web service restart does not register.
- Browser JavaScript never stores or receives the long-lived participant token.
- Browser JavaScript never calls `/api/im/*`.
- Web Management does not expose `/api/im/*` as a Browser-facing compatibility path.
- Message history is read from IM conversation facts, not stored in Web-interface.
- No new actor history, WebUI message entity, or domain/repo WebUI message store is added.

## Files

- Create: `tools/launcher/web_im_identity.py`
  - Owns the Web Management IM credential record under `runtime_files.LOCAL_ROOT / "web-management" / "im-session.json"`.
  - Validates existing token with `message_service.authenticate_im_token`.
  - Registers exactly once when no valid identity exists.
  - Uses `im-session.lock` to serialize startup in one runtime.

- Modify: `tools/launcher/web_management.py`
  - Imports and constructs `WebImIdentityProvider`.
  - Adds `/api/web/im/session`, `/api/web/im/messages`, actor-scoped `/api/web/im/events`, and `/api/web/im/conversations/direct`.
  - Removes direct `/api/im/*` forwarding from Web Management surface.
  - Keeps lower `ImHttpRouter` only as an internal/external contract helper where needed.

- Modify: `tools/launcher/assets/web-management/app.js`
  - Removes `imParticipantToken` and `ensureImParticipant`.
  - Replaces `/api/im/*` calls with `/api/web/im/*`.
  - Loads direct conversation history when a selected actor console is available.
  - Polls `/api/web/im/events` with the selected actor scope and records returned messages without Browser message-detail fetches.

- Modify: `tests/test_web_management.py`
  - Adds stable identity startup/reuse tests.
  - Adds `/api/web/im/*` projection behavior tests.
  - Adds rejection test for `/api/im/*` through Web Management.

- Modify: `tests/test_im_web_management_projection.py`
  - Replaces old passthrough expectations with no-compat surface expectations.

- Modify: `tests/web_management_ui_contract.test.js`
  - Asserts Browser assets include `/api/web/im/*`.
  - Asserts Browser assets exclude `/api/im`, `external-participants`, `imParticipantToken`, and `Authorization: Bearer`.

- Modify: `tests/web_management_ui_state.test.js`
  - Updates route builder expectations.
  - Adds message history/event projection normalization coverage.

## Tasks

### Task 1: Red Tests For No-Compat Web Surface

- [ ] Update Web Management tests so `service.handle_api("POST", "/api/im/external-participants", ...)` raises `HttpError` 404.
- [ ] Add tests that `/api/web/im/session` returns Web session metadata without `participant_token`.
- [ ] Add tests that constructing two `WebManagementService` instances in the same runtime reuses one identity record.
- [ ] Add tests that invalid identity token is replaced once and then reused.

### Task 2: Red Tests For WebUI Contract

- [ ] Update Browser contract test to fail while `app.js` contains `/api/im`, `external-participants`, `imParticipantToken`, or `Authorization`.
- [ ] Update state tests to expect `/api/web/im/events`.
- [ ] Add state tests for applying direct conversation history and event messages to the local render cache.

### Task 3: Implement Stable Web IM Identity Provider

- [ ] Add `tools/launcher/web_im_identity.py`.
- [ ] Persist identity JSON under `runtime_files.LOCAL_ROOT / "web-management"`.
- [ ] Acquire a local lock around read/validate/register/write.
- [ ] Use `message_service.authenticate_im_token` to validate persisted credentials.
- [ ] Use `message_service.register_external_participant(client_kind="web-management", display_name="BuddySwitch Web")` only when no valid credential exists.
- [ ] Never store message history in the identity record.

### Task 4: Replace Web Management IM Routes

- [ ] Add `/api/web/im/session`.
- [ ] Add `/api/web/im/messages` for Browser sends; derive sender from server-owned identity.
- [ ] Add `/api/web/im/conversations/direct` for selected actor history.
- [ ] Add actor-scoped `/api/web/im/events`; require `role_id` and `actor_id`, return only that actor direct conversation's events plus visible message payloads, and keep the Web participant cursor moving across skipped unrelated events.
- [ ] Remove `/api/im/*` forwarding from `WebManagementService.handle_api`.

### Task 5: Replace Browser IM Calls

- [ ] Remove `imParticipantToken` state.
- [ ] Remove `ensureImParticipant`.
- [ ] Build only `/api/web/im/*` URLs, with event polling scoped to the selected actor.
- [ ] Start polling after server session bootstrap, not participant registration.
- [ ] Load direct conversation history after selected actor console changes.
- [ ] Keep `imConversation` as render cache only.

### Task 6: Verification And Cleanup

- [ ] Run focused Python Web Management tests.
- [ ] Run Browser contract/state tests.
- [ ] Run lower IM router/reply-loop tests to verify the external IM contract still works.
- [ ] Run boundary tests.
- [ ] Run `rg` checks proving no WebUI `/api/im` or Browser token residue remains.
- [ ] Run `git diff --check`.
