from tests.integration.web.management_harness import *  # noqa: F401,F403


class WebManagementStableImIdentityTests(RuntimeWorkspaceTestCase):
    def _service(self, host_control: RecordingHostControl | None = None) -> WEB_MANAGEMENT.WebManagementService:
        return WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=host_control or RecordingHostControl())

    def _identity_path(self) -> Path:
        return self.runtime_state_root / "buddyswitch" / "local" / "web-management" / "im-session.json"

    def _external_identity_files(self) -> list[Path]:
        identities_dir = self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "externals"
        return sorted(identities_dir.glob("*.json")) if identities_dir.is_dir() else []

    @staticmethod
    def _seed_actor_identity_profiles(identity_routes: list[dict[str, str]]) -> None:
        for route in identity_routes:
            save_test_actor_identity_profile(actor_id=route["actor_id"], role_id=route["role_id"])

    @staticmethod
    def _instance_list_for_identity_routes(identity_routes: list[dict[str, str]]) -> dict[str, object]:
        return {
            "instances": [
                {
                    "actor_id": route["actor_id"],
                    "role": route["role_id"],
                    "status": "active",
                    "app_server_health": "healthy",
                    "thread_id": f"thread-{index}",
                    "browser_port": None,
                    "updated_at": "2026-06-26T10:10:00Z",
                    "workspace_dir": f"/tmp/buddyswitch/instances/{route['actor_id']}/workspace",
                }
                for index, route in enumerate(identity_routes)
            ]
        }

    def test_retired_web_im_routes_are_not_live(self) -> None:
        service = self._service()
        retired_prefix = "/api/web/" + "im"

        for method, path, body in (
            ("GET", retired_prefix + "/session", b""),
            ("POST", retired_prefix + "/messages", b'{"target_identity_id":"act-market-demo","content":"ping"}'),
            ("GET", retired_prefix + "/events?identity_id=act-market-demo&wait_ms=0", b""),
            ("GET", retired_prefix + "/conversations/direct?identity_id=act-market-demo&limit=20", b""),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api(method, path, body, {})
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(raised.exception.code, "NOT_FOUND")

    def test_web_im_actor_roster_does_not_create_actor_identity_profile(self) -> None:
        routes = [{"actor_id": "act-web-profile-missing", "role_id": "dev"}]
        runner = RecordingHostControl()
        runner.list_instances_response = self._instance_list_for_identity_routes(routes)["instances"]
        service = self._service(runner)

        status, payload = service.handle_api("GET", "/api/im/actors", b"", {})

        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 1)
        self.assertIsNone(identity_repo.get_actor_identity_profile("act-web-profile-missing"))

    def test_im_session_creates_one_stable_web_identity_per_runtime(self) -> None:
        first = self._service()
        first_status, first_payload = first.handle_api("GET", "/api/im/session", b"", {})
        second = self._service()
        second_status, second_payload = second.handle_api("GET", "/api/im/session", b"", {})

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertTrue(first_payload["ok"])
        self.assertEqual(first_payload["identity"], second_payload["identity"])
        self.assertEqual(first_payload["identity"]["type"], "external")
        self.assertNotIn("role_id", first_payload["identity"])
        self.assertNotIn("participant", first_payload)
        self.assertNotIn("participant", second_payload)
        self.assertNotIn("participant_token", first_payload)
        self.assertNotIn("participant_token", second_payload)
        self.assertNotIn("external_session_key", first_payload)
        self.assertNotIn("external_session_key", second_payload)
        self.assertNotIn("event_cursor", first_payload)
        self.assertNotIn("event_cursor", second_payload)
        self.assertEqual(len(self._external_identity_files()), 1)
        identity = json.loads(self._identity_path().read_text(encoding="utf-8"))
        self.assertEqual(identity["client_kind"], "web-management")
        self.assertEqual(identity["display_name"], "BuddySwitch Web")
        self.assertEqual(identity["identity"], first_payload["identity"])
        self.assertIn("external_session_key", identity)
        self.assertNotIn("participant", identity)
        self.assertNotIn("participant_token", identity)
        self.assertNotIn("event_cursor", identity)
        self.assertNotIn("messages", identity)
        self.assertNotIn("conversation", identity)
        self.assertNotIn("actor_history", identity)

    def test_invalid_web_im_identity_is_replaced_once_then_reused(self) -> None:
        first_status, first_payload = self._service().handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(first_status, 200)
        first_external_id = first_payload["identity"]["id"]
        identity_path = self._identity_path()
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["external_session_key"] = "imsk-invalid"
        identity_path.write_text(json.dumps(identity, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        replaced_status, replaced_payload = self._service().handle_api("GET", "/api/im/session", b"", {})
        reused_status, reused_payload = self._service().handle_api("GET", "/api/im/session", b"", {})

        self.assertEqual(replaced_status, 200)
        self.assertEqual(reused_status, 200)
        self.assertNotEqual(replaced_payload["identity"]["id"], first_external_id)
        self.assertEqual(replaced_payload["identity"], reused_payload["identity"])
        self.assertEqual(len(self._external_identity_files()), 2)

    def test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token(self) -> None:
        """Browser-style Web request sends target-identity IM through /api/im/messages, actor reply becomes visible through /api/im/events, browser fetches the reply through /api/im/messages/<id>, browser acks through /api/im/events/ack, and direct conversation shows both messages without exposing external_session_key."""
        actor_route = {
            "role_id": "market",
            "actor_id": self._runtime_actor_id(role="market", label="web-im-history"),
        }
        self._seed_actor_identity_profiles([actor_route])
        runner = RecordingHostControl()
        runner.list_instances_response = self._instance_list_for_identity_routes([actor_route])["instances"]
        service = self._service(runner)
        status, session = service.handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(status, 200)
        web_identity = session["identity"]

        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            side_effect=lambda **kwargs: {
                "reachability_status": "online",
                "target_identity_id": kwargs["target_identity_id"],
                "record": {"identity_id": kwargs["target_identity_id"]},
            },
        ), mock.patch.object(
            WEB_MANAGEMENT.im_actor_delivery,
            "deliver",
            return_value={"actor_handling_status": "submitted", "runtime_target": "parent", "error": None},
        ) as deliver_im_actor:
            status, sent = service.handle_api(
                "POST",
                "/api/im/messages",
                json.dumps(
                    {
                        "target_identity_id": actor_route["actor_id"],
                        "content": "ping",
                        "reply_to": None,
                    }
                ).encode("utf-8"),
                {},
            )

        self.assertEqual(status, 200, msg=sent)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", sent)
        deliver_im_actor.assert_called_once()
        self.assertNotIn("target_" + "role_id", deliver_im_actor.call_args.args[0])
        sent_message_id = sent["message"]["id"]

        reply = message_service.send_im_reply(
            sender_identity={"id": actor_route["actor_id"], "type": "actor"},
            content="pong",
            reply_to=sent_message_id,
        )
        self.assertTrue(reply["ok"], msg=reply)

        status, events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply["message"]["id"]])
        self.assertNotIn("messages", events)
        self.assertNotIn("participant_token", events)
        self.assertNotIn("external_session_key", events)
        self.assertNotIn("next_cursor", events)
        self.assertNotIn("ack", events)

        status, repeated_events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=repeated_events)
        self.assertEqual([event["message_id"] for event in repeated_events["events"]], [reply["message"]["id"]])

        reply_id = reply["message"]["id"]
        status, fetched = service.handle_api("GET", f"/api/im/messages/{reply_id}", b"", {})
        self.assertEqual(status, 200, msg=fetched)
        self.assertEqual(fetched["message"]["content"], "pong")
        self.assertNotIn("external_session_key", fetched)

        status, acked = service.handle_api(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": reply["event_id"]}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200, msg=acked)
        self.assertTrue(acked["ok"])
        self.assertNotIn("external_session_key", acked)

        status, after_ack = service.handle_api("GET", "/api/im/events?wait_ms=0", b"", {})
        self.assertEqual(status, 200, msg=after_ack)
        self.assertEqual(after_ack["events"], [])

        status, history = service.handle_api(
            "GET",
            f"/api/im/conversations/direct?identity_id={actor_route['actor_id']}&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=history)
        self.assertEqual([row["id"] for row in history["messages"]], [sent_message_id, reply_id])
        self.assertNotIn("external_session_key", history)

    def test_im_events_are_external_session_wide_and_do_not_fetch_or_ack_messages(self) -> None:
        market_actor = {
            "role_id": "market",
            "actor_id": self._runtime_actor_id(role="market", label="web-im-market"),
        }
        dev_actor = {
            "role_id": "dev",
            "actor_id": self._runtime_actor_id(role="dev", label="web-im-dev"),
        }
        self._seed_actor_identity_profiles([market_actor, dev_actor])
        runner = RecordingHostControl()
        runner.list_instances_response = self._instance_list_for_identity_routes([market_actor, dev_actor])["instances"]
        service = self._service(runner)
        session_status, session = service.handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(session_status, 200)
        web_identity = session["identity"]
        sent_by_actor: dict[str, dict[str, object]] = {}
        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            side_effect=lambda **kwargs: {
                "reachability_status": "online",
                "target_identity_id": kwargs["target_identity_id"],
                "record": {"identity_id": kwargs["target_identity_id"]},
            },
        ):
            for actor_route, content in (
                (market_actor, "market ping"),
                (dev_actor, "dev ping"),
            ):
                status, payload = service.handle_api(
                    "POST",
                    "/api/im/messages",
                    json.dumps(
                        {
                            "target_identity_id": actor_route["actor_id"],
                            "content": content,
                            "reply_to": None,
                        }
                    ).encode("utf-8"),
                    {},
                )
                self.assertEqual(status, 200, msg=payload)
                sent_by_actor[actor_route["actor_id"]] = payload

        for actor_route, content in (
            (market_actor, "market pong"),
            (dev_actor, "dev pong"),
        ):
            reply = message_service.send_im_reply(
                sender_identity={"id": actor_route["actor_id"], "type": "actor"},
                content=content,
                reply_to=sent_by_actor[actor_route["actor_id"]]["message"]["id"],
            )
            self.assertTrue(reply["ok"], msg=reply)

        status, events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0&limit=50",
            b"",
            {},
        )

        self.assertEqual(status, 200, msg=events)
        self.assertEqual(
            [event["sender_identity"]["id"] for event in events["events"]],
            [market_actor["actor_id"], dev_actor["actor_id"]],
        )
        self.assertNotIn("messages", events)

        status, repeated = service.handle_api("GET", "/api/im/events?wait_ms=0&limit=50", b"", {})
        self.assertEqual(status, 200, msg=repeated)
        self.assertEqual(
            [event["sender_identity"]["id"] for event in repeated["events"]],
            [market_actor["actor_id"], dev_actor["actor_id"]],
        )

        for event in events["events"]:
            status, fetched = service.handle_api("GET", f"/api/im/messages/{event['message_id']}", b"", {})
            self.assertEqual(status, 200, msg=fetched)
            self.assertIn(fetched["message"]["content"], {"market pong", "dev pong"})
            status, acked = service.handle_api(
                "POST",
                "/api/im/events/ack",
                json.dumps({"event_id": event["event_id"]}).encode("utf-8"),
                {},
            )
            self.assertEqual(status, 200, msg=acked)

        status, market_history = service.handle_api(
            "GET",
            f"/api/im/conversations/direct?identity_id={market_actor['actor_id']}&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=market_history)
        self.assertEqual(
            [row["content"] for row in market_history["messages"]],
            ["market ping", "market pong"],
        )

    def test_im_events_rejects_browser_supplied_cursor(self) -> None:
        service = self._service()
        service.handle_api("GET", "/api/im/session", b"", {})

        status, payload = service.handle_api("GET", "/api/im/events?cursor=imev-000000000000&wait_ms=0", b"", {})

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_PAYLOAD")
