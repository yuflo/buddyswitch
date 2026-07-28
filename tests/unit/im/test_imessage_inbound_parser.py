"""Typed iMessage inbound grammar contracts."""

from __future__ import annotations

import inspect
import unittest

from buddyswitch.launcher import imessage_channel


class ImessageInboundParserTests(unittest.TestCase):
    def test_native_reply_domain_keeps_command_like_body_opaque(self) -> None:
        parsed = imessage_channel._parse_inbound_message(
            {
                "text": "/actors",
                "thread_originator_guid": "ACTOR-BUBBLE-GUID",
                "reply_to_guid": "OTHER-CONTEXT-GUID",
            }
        )

        self.assertEqual(
            parsed,
            imessage_channel._NativeReply(
                anchor_guid="ACTOR-BUBBLE-GUID",
                body="/actors",
            ),
        )

    def test_reply_to_guid_alone_parses_top_level_send(self) -> None:
        parsed = imessage_channel._parse_inbound_message(
            {
                "text": "@act-dev-demo hello   dev",
                "reply_to_guid": "PREVIOUS-DIRECT-MESSAGE-GUID",
            }
        )

        self.assertEqual(
            parsed,
            imessage_channel._TopLevel(
                command=imessage_channel._SendToActor(
                    target_identity_id="act-dev-demo",
                    content="hello   dev",
                )
            ),
        )

    def test_exact_actors_command_parses_top_level_list(self) -> None:
        parsed = imessage_channel._parse_inbound_message({"text": " /actors "})

        self.assertEqual(
            parsed,
            imessage_channel._TopLevel(command=imessage_channel._ListActors()),
        )

    def test_non_grammar_text_parses_invalid_top_level(self) -> None:
        for text in ("plain text", "@act-dev-demo", "/actors extra"):
            with self.subTest(text=text):
                parsed = imessage_channel._parse_inbound_message({"text": text})
                self.assertEqual(
                    parsed,
                    imessage_channel._TopLevel(command=imessage_channel._InvalidTopLevel()),
                )

    def test_production_contains_no_flat_parser_residue(self) -> None:
        source = inspect.getsource(imessage_channel)

        for retired_name in (
            "_ActorsQueryIntent",
            "_ActorSendIntent",
            "_NativeReplyIntent",
            "_InvalidInputIntent",
            "_InboundIntent",
            "_parse_inbound_intent",
            "_handle_actor_mention",
        ):
            with self.subTest(retired_name=retired_name):
                self.assertNotIn(retired_name, source)


if __name__ == "__main__":
    unittest.main()
