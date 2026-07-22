"""iMessage per-message routing product contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.integration.im._imessage_fakes import (
    _FakeBuddySwitchImApi,
    _actor,
    _controller,
    _current_state,
    _row,
)


USAGE_PROMPT = "Use /actors, @actor-id <message>, or Reply to an actor message."
REPLY_UNAVAILABLE_PROMPT = "This message cannot be replied to."
REPLY_FAILED_PROMPT = "Reply failed. Try again or use @actor-id."


class ImessageRoutingTests(unittest.TestCase):
    def test_actors_lists_direct_mentions_without_selection_state(self) -> None:
        actors = [
            _actor("market", "act-market-online"),
            _actor("pm", "act-pm-online"),
        ]
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, imsg = _controller(
                Path(temp_root),
                api=_FakeBuddySwitchImApi(actors=actors),
            )

            result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            state = controller.state_store.load()

        self.assertEqual(result, {"ok": True, "status": "actors_listed", "count": 2})
        self.assertEqual(imsg.sent[-1]["text"], "@act-market-online (market)\n@act-pm-online (pm)")
        contact = state["contacts"]["sender:user-a@example.com"]
        self.assertEqual(contact["seen_inbound_keys"], ["guid:guid-actors"])
        self.assertEqual(contact["message_links"], {})
        self.assertNotIn("active_identity_id", contact)
        self.assertNotIn("pending_actor_choices", contact)

    def test_first_contact_creates_one_external_session_and_reuses_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))

            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            sent = controller.handle_inbound_message(
                _row(text="@act-market-demo hello", guid="guid-mention")
            )

        self.assertEqual(sent["status"], "delivered")
        self.assertEqual([row["external_session_key"] for row in api.created], ["imsk-1"])
        self.assertEqual(api.sent_to_actor[-1]["external_session_key"], "imsk-1")

    def test_actor_mention_sends_original_body_to_exact_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(
                _row(text="@act-dev-demo 你好 dev", guid="guid-mention")
            )

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(
            api.sent_to_actor,
            [
                {
                    "external_session_key": "imsk-1",
                    "target_identity_id": "act-dev-demo",
                    "content": "你好 dev",
                    "message_id": "msg-in-1",
                }
            ],
        )
        self.assertEqual(api.replies, [])

    def test_plain_text_and_empty_mention_only_return_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            plain = controller.handle_inbound_message(_row(text="plain message", guid="guid-plain"))
            empty = controller.handle_inbound_message(_row(text="@act-dev-demo", guid="guid-empty"))

        self.assertEqual(plain["status"], "invalid_message")
        self.assertEqual(empty["status"], "invalid_message")
        self.assertEqual([row["text"] for row in imsg.sent], [USAGE_PROMPT, USAGE_PROMPT])
        self.assertEqual(api.sent_to_actor, [])
        self.assertEqual(api.replies, [])

    def test_duplicate_inbound_guid_is_not_sent_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            row = _row(text="@act-dev-demo once", guid="guid-once")

            first = controller.handle_inbound_message(row)
            duplicate = controller.handle_inbound_message(row)

        self.assertEqual(first["status"], "delivered")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(len(api.sent_to_actor), 1)

    def test_two_contacts_keep_sessions_routes_and_dedupe_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))

            controller.handle_inbound_message(
                _row(sender="a@example.com", text="@act-dev-demo from a", guid="same-guid", chat_id="1")
            )
            controller.handle_inbound_message(
                _row(sender="b@example.com", text="@act-pm-demo from b", guid="same-guid", chat_id="2")
            )
            state = controller.state_store.load()

        self.assertEqual([row["external_session_key"] for row in api.created], ["imsk-1", "imsk-2"])
        self.assertEqual(
            [row["target_identity_id"] for row in api.sent_to_actor],
            ["act-dev-demo", "act-pm-demo"],
        )
        self.assertEqual(
            state["contacts"]["sender:a@example.com"]["route"],
            {"chat_id": "1", "sender": "a@example.com"},
        )
        self.assertEqual(
            state["contacts"]["sender:b@example.com"]["route"],
            {"chat_id": "2", "sender": "b@example.com"},
        )

    def test_native_reply_uses_thread_originator_link_and_ignores_quoted_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            controller.state_store.save(_current_state())

            result = controller.handle_inbound_message(
                _row(
                    text="直接回复我 你好呀",
                    guid="A88540A2",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                    reply_to_guid="LATEST-THREAD-ITEM-GUID",
                    reply_to_text="[Message From act-wrong]\n\n错误锚点",
                )
            )

        self.assertEqual(result["status"], "replied")
        self.assertEqual(
            api.replies,
            [
                {
                    "external_session_key": "imsk-existing",
                    "reply_to": "msg-actor-1",
                    "content": "直接回复我 你好呀",
                }
            ],
        )
        self.assertEqual(api.sent_to_actor, [])

    def test_reply_to_guid_without_thread_originator_routes_top_level_actor_send(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            controller.state_store.save(_current_state())

            result = controller.handle_inbound_message(
                _row(
                    text="@act-dev-demo top-level send",
                    guid="guid-top-level-send",
                    reply_to_guid="ACTOR-BUBBLE-GUID",
                )
            )

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(api.replies, [])
        self.assertEqual(api.sent_to_actor[-1]["target_identity_id"], "act-dev-demo")
        self.assertEqual(api.sent_to_actor[-1]["content"], "top-level send")

    def test_native_reply_domain_treats_exact_actors_text_as_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_current_state())

            result = controller.handle_inbound_message(
                _row(
                    text="/actors",
                    guid="guid-reply-actors",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )

        self.assertEqual(result["status"], "replied")
        self.assertEqual(api.replies[-1]["reply_to"], "msg-actor-1")
        self.assertEqual(api.replies[-1]["content"], "/actors")
        self.assertEqual(imsg.sent, [])

    def test_native_reply_domain_treats_leading_mention_as_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            controller.state_store.save(_current_state())

            controller.handle_inbound_message(
                _row(
                    text="@act-pm-demo still reply content",
                    guid="guid-reply-mention",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )

        self.assertEqual(api.replies[-1]["reply_to"], "msg-actor-1")
        self.assertEqual(api.replies[-1]["content"], "@act-pm-demo still reply content")
        self.assertEqual(api.sent_to_actor, [])

    def test_missing_native_reply_link_never_parses_text_or_sends_to_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(
                _row(
                    text="reply",
                    guid="guid-unmapped",
                    thread_originator_guid="UNKNOWN-GUID",
                    reply_to_text="[Message From act-dev-demo]\n\nvisible but unmapped",
                )
            )

        self.assertEqual(result["status"], "reply_unavailable")
        self.assertEqual(imsg.sent[-1]["text"], REPLY_UNAVAILABLE_PROMPT)
        self.assertEqual(api.replies, [])
        self.assertEqual(api.sent_to_actor, [])

    def test_native_reply_never_uses_another_contacts_message_link(self) -> None:
        state = _current_state()
        state["contacts"]["sender:b@example.com"] = {
            "external_session_key": "imsk-b",
            "external_identity_id": "ext-b",
            "route": {"chat_id": "10", "sender": "b@example.com"},
            "seen_inbound_keys": [],
            "message_links": {},
        }
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(state)

            result = controller.handle_inbound_message(
                _row(
                    sender="b@example.com",
                    text="reply from b",
                    guid="guid-b-reply",
                    chat_id="10",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )

        self.assertEqual(result["status"], "reply_unavailable")
        self.assertEqual(imsg.sent[-1]["text"], REPLY_UNAVAILABLE_PROMPT)
        self.assertEqual(api.replies, [])

    def test_multiple_native_replies_share_one_anchor_without_target_send_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_current_state())

            first = controller.handle_inbound_message(
                _row(
                    text="FIRST",
                    guid="guid-first",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )
            second = controller.handle_inbound_message(
                _row(
                    text="SECOND",
                    guid="guid-second",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )
            state = controller.state_store.load()

        self.assertEqual(first["status"], "replied")
        self.assertEqual(second["status"], "replied")
        self.assertEqual([call["reply_to"] for call in api.replies], ["msg-actor-1", "msg-actor-1"])
        self.assertEqual([call["content"] for call in api.replies], ["FIRST", "SECOND"])
        self.assertEqual(api.sent_to_actor, [])
        self.assertEqual(imsg.sent, [])
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["message_links"]["ACTOR-BUBBLE-GUID"],
            {"message_id": "msg-actor-1", "event_id": "imev-actor-1"},
        )

    def test_native_reply_api_failure_has_no_target_send_fallback_or_one_shot_guidance(self) -> None:
        api = _FakeBuddySwitchImApi()
        api.reply_results.append(
            {
                "ok": False,
                "error": {
                    "code": "E_IM_TARGET",
                    "message": "target actor is not currently reachable",
                },
            }
        )
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, imsg = _controller(Path(temp_root), api=api)
            controller.state_store.save(_current_state())

            result = controller.handle_inbound_message(
                _row(
                    text="retryable reply",
                    guid="guid-reply-failed",
                    thread_originator_guid="ACTOR-BUBBLE-GUID",
                )
            )

        self.assertEqual(result["status"], "reply_failed")
        self.assertEqual(imsg.sent[-1]["text"], REPLY_FAILED_PROMPT)
        self.assertEqual(len(api.replies), 1)
        self.assertEqual(api.sent_to_actor, [])

    def test_from_me_and_empty_rows_are_ignored_without_session_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            from_me = controller.handle_inbound_message(
                _row(text="@act-dev-demo ignored", guid="guid-self", is_from_me=True)
            )
            empty = controller.handle_inbound_message(_row(text="   ", guid="guid-empty"))

        self.assertEqual(from_me["status"], "ignored_from_me")
        self.assertEqual(empty["status"], "ignored_empty")
        self.assertEqual(api.created, [])
        self.assertEqual(imsg.sent, [])
