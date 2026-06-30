# iMessage Channel / IM API Boundary Optimization Final Acceptance

Date: 2026-06-30

## Completion Summary

The memo target is complete in this worktree.

End-to-end contract now proven by automated worker coverage:

```text
iMessage normal actor message
  -> External IM API send / actor wake path
  -> immediate /actors control reply while outbound poll is blocked
  -> delayed actor reply returns once to the same iMessage chat
```

Primary proof:

- `tests/test_imessage_channel.py::ImessageChannelTests::test_worker_keeps_control_prompt_prompt_while_delayed_reply_returns_once_to_same_chat`

## Memo Task Status

| Requirement | Status | Evidence |
| --- | --- | --- |
| External IM events are not acknowledged by read | Complete | `tests/test_im_product_core.py::test_external_connection_reads_actor_reply_once_without_client_cursor`; `tests/test_external_im_session.py::test_session_reads_actor_reply_once_without_client_cursor`; `tests/test_im_http_router.py::test_external_http_contract_send_events_get_and_mark` |
| Ack advances connection cursor through IM API | Complete | `message_service.ack_external_connection_event()` tests; HTTP `POST /api/im/events/ack` tests |
| Non-visible event ack is rejected | Complete | `tests/test_im_product_core.py::test_external_connection_ack_rejects_non_visible_event_without_advancing_cursor` |
| Out-of-order event ack is rejected | Complete | `tests/test_im_product_core.py::test_external_connection_ack_rejects_out_of_order_consumable_event` |
| Web projection does not expose cursor/ack/connection details | Complete | `tests/test_web_management.py` Web IM identity/event assertions; Node UI state/contract tests |
| iMessage worker inbound and outbound loops are split | Complete | `tests/test_imessage_channel.py::test_worker_processes_actors_while_outbound_poll_is_blocked` |
| Late actor reply arrives without a new inbound iMessage | Complete | `tests/test_imessage_channel.py::test_worker_delivers_late_reply_without_new_inbound_message` |
| Normal message, immediate `/actors`, delayed reply once to same chat | Complete | `tests/test_imessage_channel.py::test_worker_keeps_control_prompt_prompt_while_delayed_reply_returns_once_to_same_chat` |
| iMessage event ack happens only after transport projection | Complete | `tests/test_imessage_channel.py::test_actor_reply_is_prefixed_and_sent_to_recorded_route_once` |
| Failed `imsg.send` does not ack | Complete | `tests/test_imessage_channel.py::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails` |
| Ack failure after send does not duplicate iMessage | Complete | `tests/test_imessage_channel.py::test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure` |
| Missing route is acked as not projectable after fetch | Complete | `tests/test_imessage_channel.py::test_poll_outbound_acks_unrouteable_event_after_fetch` |
| Message fetch failure does not ack | Complete | `tests/test_imessage_channel.py::test_poll_outbound_does_not_ack_when_message_fetch_fails` |
| No Central IM internals imported into iMessage channel | Complete | `tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals` |
| No old serial worker live-surface residue | Complete | `tests/test_imessage_channel.py::ImessageChannelResidueTests` and final `rg` scan |
| Smoke runbook includes delayed-control scenario | Complete | `docs/spec/imessage-channel-smoke-runbook.md`; residue test asserts exact steps |

## Added Or Modified Tests

Modified:

- `tests/test_im_product_core.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_web_management.py`
- `tests/test_im_external_reply_loop.py`
- `tests/test_external_im_projection_contract.py`
- `tests/test_imessage_channel.py`

New key coverage:

- Explicit External IM ack contract.
- Web scoped event consumption with direct conversation restore.
- Split iMessage inbound/outbound worker loops.
- Ack-after-iMessage-send projection semantics.
- Combined iMessage delayed-control contract.
- Live-surface residue for old serial semantics.

## Verification

Final compile:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py scripts/env/services/messages.py
```

Result: passed.

Final focused Python verification:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py tests/test_imessage_channel.py
```

Result:

```text
121 passed, 74 subtests passed in 113.06s
```

Final Node UI verification:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result:

```text
2 test files passed; 0 failed
```

Final residue scan:

```bash
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|handle_inbound_message\\(row\\).*poll_outbound_once|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S -g '!docs/spec/imessage-channel-im-api-boundary-optimization/**'
```

Result: no hits.

## Live Smoke

Not run in this pass. The automated worker tests cover the delayed-control contract without starting long-lived Web or `imsg watch` processes.

If a live smoke is run later, use `docs/spec/imessage-channel-smoke-runbook.md`; it now requires:

- normal actor message;
- immediate `/actors` before actor reply;
- prompt actor-list reply;
- original actor reply once in the same chat;
- Web shutdown and residual `imsg watch --json` process check.

## Residual Risk

- Cross-system atomicity remains impossible between Messages.app delivery, local channel state save, and IM API ack. The implementation saves local transport idempotency before ack, so ack retry does not duplicate after that point.
- Web event polling remains selected-actor scoped, not a cross-actor notification queue. Off-scope events consumed by Web polling remain available through direct conversation restore.
- Live macOS/iMessage behavior still depends on local `imsg` and Messages.app state; final live confidence requires the smoke runbook when that environment is available.

## Final State Statement

- No old serial `handle inbound -> wait for reply` worker path remains.
- No compatibility flag or dual worker mode was introduced.
- No Central IM cursor logic was moved into `tools/launcher/imessage_channel.py`.
- No iMessage channel import from `env.services.messages` or `env.repos.messages` exists.
- Live surfaces no longer teach old serial reply-wait semantics.
